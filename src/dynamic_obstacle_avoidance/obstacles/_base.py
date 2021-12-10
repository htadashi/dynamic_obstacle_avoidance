"""
Basic class to represent obstacles
"""
import time
import warnings
import sys
from math import sin, cos, pi, ceil

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache

import numpy as np
import numpy.linalg as LA

import matplotlib.pyplot as plt

from scipy.spatial.transform import Rotation  # scipy rotation

from vartools.angle_math import angle_difference_directional
from vartools.linalg import get_orthogonal_basis
from vartools.angle_math import periodic_weighted_sum
from vartools.states import ObjectPose
from vartools.directional_space import get_angle_space_inverse

from .hull_storer import ObstacleHullsStorer


class GammaType(Enum):
    """Different gamma-types for caclulation of 'distance' / barrier-measure.
    The gamma value is given in [1 - infinity] outside the obstacle
    except (!) the barrier type is from"""

    RELATIVE = auto()
    EUCLEDIAN = auto()
    SCALED_EUCLEDIAN = auto()
    BARRIER = auto()


class Obstacle(ABC):
    """(Virtual) base class of obstacles
    This class defines obstacles to modulate the DS around it
    """

    id_counter = 0
    active_counter = 0
    # TODO: clean up & cohesion vs inhertiance! (decouble /lighten class)

    def __repr__(self):
        repr_str = (
            f"{type(self).__name__}(\n"
            + f"center_position=np.{repr(self.center_position)},\n"
        )

        if self.orientation:
            repr_str += f"orientation={float(self.orientation)},\n"

        if LA.norm(self.linear_velocity):
            repr_str += f"linear_velocity=np.{repr(self.linear_velocity)},\n"

        if LA.norm(self.angular_velocity):
            repr_str += f"angular_velocity={repr(float(self.angular_velocity))},\n"

        if self.is_boundary:
            repr_str += f"is_boundary={self.is_boundary},\n"

        if hasattr(self, "axes_length"):
            repr_str += f"axes_length=np.{repr(self.axes_length)},\n"

        elif hasattr(self, "edge_points"):
            repr_str += f"edge_points=np.{repr(self.edge_points)},\n"

        repr_str += ")\n"

        return repr_str

    def __init__(
        self,
        center_position=None,
        orientation=None,
        tail_effect=True,
        has_sticky_surface=True,
        repulsion_coeff=1,
        reactivity=1,
        name=None,
        is_dynamic=False,
        is_deforming=False,
        margin_absolut=0,
        dimension=None,
        linear_velocity=None,
        angular_velocity=None,
        xd=None,
        w=None,
        func_w=None,
        func_xd=None,
        x_start=0,
        x_end=0,
        timeVariant=False,
        Gamma_ref=0,
        is_boundary=False,
        gamma_distance=None,
        sigma=None,
        relative_hull_extension_margin=0.1,
    ):

        if name is None:
            self.name = f"obstacle_{Obstacle.id_counter}"
        else:
            self.name = name

        self.is_boundary = is_boundary

        self.position = center_position
        self.center_position = self.position

        # Dimension of space
        self.dim = len(self.center_position)

        # Relative Reference point // Dyanmic center
        self.reference_point = np.zeros(self.dim)  # TODO remove and rename
        # Margin
        if sigma is not None:
            raise Exception("Remove / rename sigma argument.")
        self.sigma = 1  # TODO: rename sigma argument

        self.relative_hull_extension_margin = relative_hull_extension_margin

        self.tail_effect = tail_effect  # Modulation if moving away behind obstacle
        self.has_sticky_surface = has_sticky_surface

        self._rotation_matrix = None
        self.orientation = orientation

        self.resolution = 0  # Resolution of drawing

        self._boundary_points = None  # Numerical drawing of obstacle boundarywq
        self._boundary_points_margin = None  # Obstacle boundary plus margin!

        self.timeVariant = timeVariant
        if self.timeVariant:
            self.func_xd = 0
            self.func_w = 0

        if angular_velocity is None:
            if w is None:
                if self.dim == 2:
                    angular_velocity = 0
                elif self.dim == 3:
                    angular_velocity = np.zeros(self.dim)
                else:
                    import pdb

                    pdb.set_trace()
                    raise ValueError("Define angular velocity for higher dimensions.")
            else:
                angular_velocity = w
        self.angular_velocity_const = angular_velocity

        if linear_velocity is None:
            if xd is None:
                self.linear_velocity = np.zeros(self.dim)
            else:
                self.linear_velocity = xd
        else:
            self.linear_velocity = linear_velocity

        if angular_velocity is None:
            self.angular_velocity = np.zeros(self.dim)
        else:
            self.angular_velocity = angular_velocity

        # Special case of moving obstacle (Create attribute [state])
        if (
            sum(np.abs(self.linear_velocity))
            or np.sum(self.angular_velocity)
            or self.timeVariant
        ):
            # Dynamic simulation - assign varibales:
            self.x_start = x_start
            self.x_end = x_end
            self.always_moving = False
        else:
            self.x_start = 0
            self.x_end = 0
            self.always_moving = False

        self.update_timestamp()

        # Set reference point value to None
        self.reset_relative_reference()

        self.Gamma_ref = Gamma_ref

        self.is_convex = False  # Needed?
        self.is_non_starshaped = False

        # Allows to track which obstacles need an update on the reference point search
        self.has_moved = True
        self.is_dynamic = is_dynamic

        self.is_deforming = is_deforming

        if self.is_deforming:
            self.inflation_speed_radial = 0

        # Repulsion coefficient to actively move away from obstacles (if possible)
        self.repulsion_coeff = repulsion_coeff
        self.reactivity = reactivity

        # Distance which decides over 'proportional' factor for gamma
        self.gamma_distance = gamma_distance

        Obstacle.id_counter += 1  # New obstacle created
        Obstacle.active_counter += 1

        # Needed for drawing polygon
        self.obs_polygon = None

        # Pass as pose-reference to the storer
        self.shapely = ObstacleHullsStorer(self)
        self._margin_absolut = margin_absolut

        self._reference_point_is_inside = True

    def __del__(self):
        Obstacle.active_counter -= 1

    @property
    def dimension(self):
        return self.dim

    @dimension.setter
    def dimension(self, value):
        self.dim = value

    @property
    def repulsion_coeff(self):
        return self._repulsion_coeff

    @repulsion_coeff.setter
    def repulsion_coeff(self, value):
        # Coefficient > 1 are accepted;
        # Good range is in [1, 2]
        # if value < 1.0:
        self._repulsion_coeff = value

    @property
    def local_relative_reference_point(self):
        return self._relative_reference_point

    @local_relative_reference_point.setter
    def local_relative_reference_point(self, value):
        self._relative_reference_point = value

    @property
    def global_relative_reference_point(self):
        if self._relative_reference_point is None:
            return self.center_position
        else:
            return self.transform_relative2global(self._relative_reference_point)

    @global_relative_reference_point.setter
    def global_relative_reference_point(self, value):
        if value is None:
            self._relative_reference_point = None
        else:
            self._relative_reference_point = self.transform_global2relative(value)

    def get_reference_point_with_margin(self):
        """Get reference point projected with the additional margin (in the local frame)."""
        ref_norm = LA.norm(self.reference_point)

        if not ref_norm:
            return self.reference_point

        dist_max = self.get_maximal_distance() * self.relative_hull_extension_margin

        reference_point_temp = self.reference_point * (1 + dist_max / ref_norm)

        return reference_point_temp

    def is_reference_point_inside(self):
        ref_extended = self.get_reference_point_with_margin()
        return (
            self.get_gamma(
                ref_extended,
                in_global_frame=False,
                with_reference_point_expansion=False,
            )
            < 1
        )

    @property
    def reference_point_is_inside(self):
        # Depreciated -> evalute in realtime
        return self._reference_point_is_inside

    @reference_point_is_inside.setter
    def reference_point_is_inside(self, value):
        # Depreciated -> evalute in realtime
        self._reference_point_is_inside = value

    @property
    def global_reference_point(self):
        # Rename kernel-point?
        return self.transform_relative2global(self._reference_point)

    @property
    def local_reference_point(self):
        # Rename kernel-point?
        return self._reference_point

    @local_reference_point.setter
    def local_reference_point(self, value):
        # Rename kernel-point?
        self._reference_point = value

    @property
    def reference_point(self):
        # Rename kernel-point?
        return self._reference_point

    @reference_point.setter
    def reference_point(self, value):
        self._reference_point = value

    @property
    def pose(self):
        return ObjectPose(position=self.position, orientation=self.orientation)

    @property
    def orientation(self):
        return self._orientation

    @orientation.setter
    def orientation(self, value):
        if value is None:
            self._orientation = value
            return

        if self.dim == 2:
            self._orientation = value
            self.compute_rotation_matrix()

        elif self.dim == 3:
            if not isinstance(value, Rotation):
                raise TypeError("Use 'scipy - Rotation' type for 3D orientation.")
            self._orientation = value

        else:
            if value is not None and np.sum(np.abs(value)):  # nonzero value
                warnings.warn("Rotation for dimensions > 3 not defined.")
            self._orientation = value

    @property
    def position(self):
        return self.center_position

    @position.setter
    def position(self, value):
        self.center_position = value

    @property
    def center_position(self):
        return self._center_position

    @center_position.setter
    def center_position(self, value):
        self._center_position = np.array(value)

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        self._timestamp = value

    def update_timestamp(self):
        self._timestamp = time.time()

    @property
    def xd(self):  # TODO: remove
        warnings.warn("'xd' is an outdated name use 'lienar_velocity' instead.")
        breakpoint()
        return self._linear_velocity_const

    @property
    def linear_velocity(self) -> np.ndarray:
        return self._linear_velocity

    @linear_velocity.setter
    def linear_velocity(self, value: np.ndarray):
        self._linear_velocity = value

    @property
    def angular_velocity(self) -> np.ndarray:
        return self._angular_velocity

    @angular_velocity.setter
    def angular_velocity(self, value: np.ndarray):
        self._angular_velocity = value

    @property
    def boundary_points(self):
        return self._boundary_points

    @boundary_points.setter
    def boundary_points(self, value):
        self._boundary_points = value

    @property
    def boundary_points_local(self):
        return self._boundary_points

    @boundary_points_local.setter
    def boundary_points_local(self, value):
        self._boundary_points = value

    @property
    def x_obs(self):
        warnings.warn("Outdated name 'x_obs'")
        return self.boundary_points_global_closed

    @property
    def boundary_points_global_closed(self):
        boundary = self.boundary_points_global
        return np.hstack((boundary, boundary[:, 0:1]))

    @property
    def boundary_points_global(self):
        return self.transform_relative2global(self._boundary_points)

    @property
    def boundary_points_margin_local(self):
        return self._boundary_points_margin

    @boundary_points_margin_local.setter
    def boundary_points_margin_local(self, value):
        self._boundary_points_margin = value

    @property
    def x_obs_sf(self):
        warnings.warn("Outdated name 'x_obs_sf'")
        return self.boundary_points_margin_global_closed

    @property
    def boundary_points_margin_global(self):
        return self.transform_relative2global(self._boundary_points_margin)

    @property
    def boundary_points_margin_global_closed(self):
        boundary = self.boundary_points_margin_global
        return np.hstack((boundary, boundary[:, 0:1]))

    def transform_global2relative(self, position):
        """Transform a position from the global frame of reference
        to the obstacle frame of reference"""
        # TODO: transform this into wrapper / decorator
        if not position.shape[0] == self.dim:
            raise ValueError("Wrong position dimensions")

        if self.dim == 2:
            if len(position.shape) == 1:
                position = position - np.array(self.center_position)
                if self._rotation_matrix is None:
                    return position
                return self._rotation_matrix.T.dot(position)

            elif len(position.shape) == 2:
                n_points = position.shape[1]
                position = position - np.tile(self.center_position, (n_points, 1)).T
                if self._rotation_matrix is None:
                    return position
                return self._rotation_matrix.T.dot(position)

            else:
                raise ValueError("Unexpected position-shape")

        elif self.dim == 3:
            if len(position.shape) == 1:
                position = position - self.center_position
                if self._orientation is None:
                    return position
                return self._orientation.inv().apply(position)

            elif len(position.shape) == 2:
                n_points = position.shape[1]
                position = position.T - np.tile(self.center_position, (n_points, 1))
                if self._orientation is None:
                    return position.T
                return self._orientation.inv().apply(position).T
            else:
                raise ValueError("Unexpected position shape.")

        else:
            warnings.warn(
                "Rotation for dimensions {} need to be implemented".format(self.dim)
            )
            return position

    def transform_relative2global(self, position):
        """Transform a position from the obstacle frame of reference
        to the global frame of reference"""
        if not isinstance(position, (list, np.ndarray)):
            raise TypeError(
                "Position={} is of type {}".format(position, type(position))
            )

        if self.dim == 2:
            if len(position.shape) == 1:
                if self._rotation_matrix is not None:
                    position = self._rotation_matrix.dot(position)
                return position + self.center_position

            elif len(position.shape) == 2:
                n_points = position.shape[1]
                if self._rotation_matrix is not None:
                    position = self._rotation_matrix.dot(position)
                return position + np.tile(self.center_position, (n_points, 1)).T

            else:
                raise ValueError("Unexpected position-shape")

        elif self.dim == 3:
            if len(position.shape) == 1:
                if self._orientation is not None:
                    position = self._orientation.apply(position)
                return position + self.center_position

            elif len(position.shape) == 2:
                n_points = position.shape[1]
                if self._orientation is not None:
                    position = self._orientation.apply(position.T).T
                return position + np.tile(self.center_position, (n_points, 1)).T

            else:
                raise ValueError("Unexpected position-shape")

        else:
            warnings.warn(
                "Rotation for dimensions {} need to be implemented".format(self.dim)
            )
            return position

    def transform_relative2global_dir(self, direction):
        """Transform a direction, velocity or relative position to the global-frame"""
        if self._orientation is None:
            return direction

        if self.dim == 2:
            return self._rotation_matrix.dot(direction)

        elif self.dim == 3:
            return self._orientation.apply(direction.T).T

        else:
            warnings.warn("Not implemented for higer dimensions")
            return direction

    def transform_global2relative_dir(self, direction):
        """Transform a direction, velocity or relative position to the obstacle-frame"""
        if self._orientation is None:
            return direction

        if self.dim == 2:
            return self._rotation_matrix.T.dot(direction)

        elif self.dim == 3:
            return self._orientation.inv.apply(direction.T).T

        else:
            warnings.warn("Not implemented for higer dimensions")
            return direction

    def transform_global2relative_matr(self, matrix):
        if self.dim > 3:
            warnings.warn("Not implemented for higer dimensions")
            return matrix
        return self._rotation_matrix.T.dot(matrix).dot(self._rotation_matrix)

    def transform_relative2global_matr(self, matrix):
        if self.dim > 3:
            warnings.warn("Not implemented for higer dimensions")
            return matrix
        return self._rotation_matrix.dot(matrix).dot(self._rotation_matrix.T)

    @property
    def margin_absolut(self):
        return self._margin_absolut

    @margin_absolut.setter
    def margin_absolut(self, value):
        self._margin_absolut = value

        if not self.is_reference_point_inside():
            self.extend_hull_around_reference()

    # @abstractmethod
    def create_shapely(self):
        raise NotImplementedError()

    def mirror_local_position_on_boundary(
        self,
        position: np.ndarray,
        local_radius: np.ndarray = None,
        pos_norm: np.ndarray = None,
    ) -> np.ndarray:
        """Returns the position (in the local frame) mirrored on the surface of the obstacle.
        i.e. positions outside will end up outside (and vice versa)."""
        if pos_norm is None:
            pos_norm = LA.norm(position)

        if not pos_norm:
            # Return a point very far away, when the point is at the center
            position = np.zeros(position.shape)
            position[0] = sys.float_info.max
            return position

        if local_radius is None:
            local_radius = self.get_local_radius(position)
        return position * (local_radius / (pos_norm * pos_norm))

    @abstractmethod
    def get_normal_direction(
        self, position: np.ndarray, in_global_frame: bool = False
    ) -> np.ndarray:
        """Get normal direction to the surface.
        IMPORTANT: Based on convention normal.dot(reference)>0 ."""
        raise NotImplementedError("Implement function in child-class of <Obstacle>.")

    # @abstractmethod
    def get_local_radius(self, position, in_local_frame: bool):
        raise NotImplementedError("Not implemented for base-class.")

    # @abstractmethod
    def get_surface_point(self, position, in_local_frame: bool):
        raise NotImplementedError("Not implemented for base-class.")

    # Store five previous values
    # @lru_cache(maxsize=5)
    @abstractmethod
    def get_gamma(self, position, with_reference_point_expansion=True):
        pass

    def get_baoundary_normal_direction(self, *args, **kwargs):
        return (-1) * self.get_normal_direction(*args, **kwargs)

    # @abstractmethod
    def draw_obstacle(self, n_resolution=20):
        """Create obstacle boundary points and stores them as attribute."""
        raise Exception("Outdated function - replaced with plot2D")

    def plot2D(
        self,
        ax,
        # fill_color="#00ff00ff",
        fill_color="#b07c7c",
        outline_color=None,
        plot_center_position=True,
        plot_reference_position=True,
    ):
        """Plots obstacle on given axes."""
        if self.dimension != 2:
            raise Exception("Only implemented for 2D case.")

        # Get inside one
        shapely_outer = self.shapely.get_global_with_everything_as_array()
        shapely_core = self.shapely.get_global_without_margin_as_array()

        ax.plot(shapely_outer[0, :], shapely_outer[1, :], "k--", linewidth=2)
        ax.plot(shapely_core[0, :], shapely_cor[e1, :], "k--", linewidth=2)

        inner_margin = np.array(insidely_.xy)

        # obs_polygon = plt.Polygon(x_obs.T, zorder=-3)
        if fill_color is not None:
            self.obs_polygon = plt.Polygon(inner_margin.T)
            self.obs_polygon.set_color(fill_color)

            ax.add_patch(self.obs_polygon)

            # Somehow only appears when additionally a 'plot is generated' (BUG?)
            ax.plot([], [])

        if outline_color is not None:
            ax.plot(inner_margin[0, :], inner_margin[1, :], "-", color=outline_color)

        if plot_center_position:
            ax.plot(
                self.center_position[0],
                self.center_position[1],
                "k.",
                markeredgewidth=4,
                markersize=13,
            )

        if plot_reference_position:
            if self.reference_point is not None and not np.isclose(
                LA.norm(self.reference_point), 0
            ):
                ref_point = self.global_reference_point
                ax.plot(
                    ref_point[0],
                    ref_point[1],
                    "k+",
                    markeredgewidth=4,
                    markersize=13,
                )

    def get_surface_derivative_angle_num(
        self,
        angle_dir,
        null_dir=None,
        NullMatrix=None,
        in_global_frame=False,
        rel_delta_dir=1e-6,
    ):
        """Numerical evaluation of surface derivative."""
        # TODO: make global frame evaluation more efficient
        # TODO: get surface intersection based on direction

        if NullMatrix is None:
            NullMatrix = get_orthogonal_basis(null_dir)

        point = get_angle_space_inverse(angle_dir, NullMatrix=NullMatrix)
        local_radius = self.get_local_radius_point(
            direction=point, in_global_frame=in_global_frame
        )

        delta_dir = np.linalg.norm(local_radius - self.center_position) * rel_delta_dir

        surf_derivs = np.zeros((angle_dir.shape[0], self.dim))
        for dd in range(angle_dir.shape[0]):
            delta_vec = np.zeros(angle_dir.shape[0])
            delta_vec[dd] = delta_dir

            point_high = get_angle_space_inverse(
                angle_dir + delta_vec, NullMatrix=NullMatrix
            )
            point_high = self.get_local_radius_point(
                direction=point_high, in_global_frame=in_global_frame
            )
            # point_high = np.linalg.norm(local_radius)*point_high

            point_low = get_angle_space_inverse(
                angle_dir - delta_vec, NullMatrix=NullMatrix
            )
            point_low = self.get_local_radius_point(
                direction=point_low, in_global_frame=in_global_frame
            )
            # point_low = np.linalg.norm(local_radius)*point_low

            surf_derivs[dd, :] = ((point_high - point_low) / (2 * delta_dir)).T

        # if in_global_frame:
        # surf_derivs = self.transform_relative2global_dir(surf_derivs)

        return surf_derivs

    def get_normal_derivative_angle_num(
        self,
        angle_dir,
        null_dir=None,
        NullMatrix=None,
        in_global_frame=False,
        delta_dir=1e-6,
    ):
        """Numerical evaluation of surface derivative."""
        # TODO: make global frame evaluation more efficient
        # TODO: get surface intersection based on direction

        if NullMatrix is None:
            NullMatrix = get_orthogonal_basis(null_dir)

        norm_derivs = np.zeros((angle_dir.shape[0], self.dim))

        for dd in range(angle_dir.shape[0]):
            delta_vec = np.zeros(angle_dir.shape[0])
            delta_vec[dd] = delta_dir

            point_high = get_angle_space_inverse(
                angle_dir + delta_vec, NullMatrix=NullMatrix
            )
            normal_high = self.get_local_radius_point(
                direction=point_high, in_global_frame=in_global_frame
            )
            # point_high = np.linalg.norm(local_radius)*point_high

            point_low = get_angle_space_inverse(
                angle_dir - delta_vec, NullMatrix=NullMatrix
            )
            normal_low = self.get_local_radius_point(
                direction=point_low, in_global_frame=in_global_frame
            )
            # point_low = np.linalg.norm(local_radius)*point_low
            norm_derivs[dd, :] = ((normal_high - normal_low) / (2 * delta_dir)).T
        # if in_global_frame:
        # norm_derivs = self.transform_relative2global_dir(norm_derivs)
        return norm_derivs

    def compute_rotation_matrix(self):
        # TODO - replace with quaternions
        # Find solution for higher dimensions
        if self.dim != 2:
            warnings.warn("Orientation matrix only used for useful for 2-D rotations.")
            return

        orientation = self._orientation
        self._rotation_matrix = np.array(
            [
                [cos(orientation), -sin(orientation)],
                [sin(orientation), cos(orientation)],
            ]
        )

    def set_reference_point(
        self, position: np.ndarray, in_global_frame: bool = False
    ) -> None:  # Inherit
        """Defines reference point.
        It is used to create reference direction for the modulation of the system."""
        if in_global_frame:
            position = self.transform_global2relative(position)
        self.reference_point = position
        if not self.is_boundary:
            self.extend_hull_around_reference()

    def extend_hull_around_reference(self):
        """Updates the obstacles such that they are star-shaped with respect to the reference
        point."""
        raise NotImplementedError("Implement for fully functional child class.")

    def do_velocity_step(self, delta_time: float) -> None:
        if self.linear_velocity is not None:
            self.position = self.position + self.linear_velocity * delta_time

        if self.angular_velocity is not None:
            if self.dimension == 2:
                self.orientation = self.orientation + self.angular_velocity * delta_time
            else:
                raise NotImplementedError("Angular velocity step not defined for d>2")

    def move_obstacle_to_referencePoint(self, position, in_global_frame=True):
        if not in_global_frame:
            position = self.transform_relative2global(position)

        self.center_position = position

        # self.reference_point = position
        # self.center_dyn = self.reference_point

    def move_center(self, position, in_global_frame=True):
        """Change (center) position of the system.
        Note that all other variables are relative."""

        if not in_global_frame:
            position = self.transform_relative2global(position)

        self.center_position = position

    def update_position(self, t, dt):
        # Inherit
        # TODO - implement function dependend movement (yield), nonlinear integration
        # Euler / Runge-Kutta integration
        # TODO: make one updater only & update also shapely

        lin_vel = self.get_linear_velocity(t)  # nonzero
        if not (lin_vel is None or np.sum(np.abs(lin_vel)) < 1e-8):
            self.center_position = self.center_position + dt * lin_vel
            self.has_moved = True

        ang_vel = self.get_angular_velocity(t)  # nonzero
        if not (ang_vel is None or np.sum(np.abs(ang_vel)) < 1e-8):
            self.orientation = self.orientation + dt * ang_vel
            self.compute_rotation_matrix()
            self.has_moved = True

        if self.has_moved:
            self.draw_obstacle()

    def update_position_and_orientation(
        self,
        position,
        orientation,
        k_position=0.9,
        k_linear_velocity=0.9,
        k_orientation=0.9,
        k_angular_velocity=0.9,
        time_current=None,
        reset=False,
    ):
        """Updates position and orientation. Additionally calculates linear and angular velocity based on the passed timestep.
        Updated values for pose and twist are filetered.

        Input:
        - Position (2D) &
        - Orientation (float)"""
        if self.dim > 2:
            raise NotImplementedError("Implement for dimension >2.")

        # TODO implement Kalman filter
        if time_current is None:
            time_current = time.time()

        if reset:
            self.center_position = position
            self.orientation = orientation
            self.linear_velocity = np.zeros(self.dim)
            self.angular_velocity = np.zeros(self.dim)
            self.draw_obstacle()
            return

        dt = time_current - self.timestamp

        if isinstance(position, list):
            position = np.array(position)

        if self.dim == 2:
            # 2D navigation, but 3D sensor input
            new_linear_velocity = (position - self.position) / dt

            # Periodicity of oscillation
            delta_orientation = angle_difference_directional(
                orientation, self.orientation
            )
            new_angular_velocity = delta_orientation / dt
            # import pdb; pdb.set_trace()
            self.linear_velocity = (
                k_linear_velocity * self.linear_velocity
                + (1 - k_linear_velocity) * new_linear_velocity
            )
            self.center_position = k_position * (
                self.linear_velocity * dt + self.center_position
            ) + (1 - k_position) * (position)

            # Periodic Weighted Average
            self.angular_velocity = (
                k_angular_velocity * self.angular_velocity
                + (1 - k_angular_velocity) * new_angular_velocity
            )

            self.orientation = periodic_weighted_sum(
                angles=[
                    self.angular_velocity * dt + self.orientation,
                    orientation,
                ],
                weights=[k_orientation, (1 - k_orientation)],
            )
        self.timestamp = time_current
        self.draw_obstacle()  # Really needed?

        self.has_moved = True

    @staticmethod
    def are_lines_intersecting(direction_line, passive_line):
        # TODO only return intersection point or None
        # solve equation line1['point_start'] + a*line1['direction'] = line2['point_end'] + b*line2['direction']
        connection_direction = np.array(direction_line["point_end"]) - np.array(
            direction_line["point_start"]
        )
        connection_passive = np.array(passive_line["point_end"]) - np.array(
            passive_line["point_start"]
        )
        connection_matrix = np.vstack((connection_direction, -connection_passive)).T

        if LA.det(connection_matrix):  # nonzero value
            direction_factors = LA.inv(connection_matrix).dot(
                np.array(passive_line["point_start"])
                - np.array(direction_line["point_start"])
            )

            # Smooth because it's a tangent
            if direction_factors[0] >= 0:
                if direction_factors[1] >= 0 and LA.norm(
                    direction_factors[1] * connection_passive
                ) <= LA.norm(connection_passive):

                    return True, LA.norm(direction_factors[0] * connection_direction)
        return False, -1

    def get_obstacle_radius(
        self, position, in_global_frame=False, Gamma=None
    ):  # Inherit
        # TODO: remove since looping...
        if in_global_frame:
            position = self.transform_global2relative(position)

        if Gamma is not None:
            Gamma = self.get_gamma(position)
        dist_to_center = LA.norm(position)

        return dist_to_center / Gamma

    def get_reference_point(self, in_global_frame=False):
        if in_global_frame:
            return self.transform_relative2global(self.reference_point)
        else:
            return self.reference_point

    def set_relative_gamma_at_position(
        self,
        position,
        relative_gamma,
        gammatype="proportional",
        in_global_frame=True,
    ):
        """Store the relative gamma of a corresponding position."""
        if not in_global_frame:
            position = self.transform_relative2global(position)
        self._relative_gamma_position = position
        self._relative_gamma = relative_gamma

    def get_relative_gamma_at_position(
        self, position, gammatype="proportional", in_global_frame=True
    ):
        """Returns relative gamma if position corresponds to stored one
        returns None if this is not the case."""
        if not in_global_frame:
            position = self.transform_relative2global(position)

        if np.allclose(position, self._relative_gamma_position):
            return self._relative_gamma
        else:
            return None

    def reset_relative_reference(self):
        self._relative_reference_point = None
        self._relative_gamma_position = None
        self._relative_gamma = None

    @property
    def has_relative_gamma(self):
        return self._relative_gamma is not None

    def get_angle2dir(self, position_dir, tangent_dir, needs_normalization=True):
        if needs_normalization:
            if len(position_dir.shape) > 1:
                position_dir /= np.tile(LA.norm(position_dir, axis=0), (self.dim, 1))
                tangent_dir /= np.tile(LA.norm(tangent_dir, axis=0), (self.dim, 1))
                angle_arccos = np.sum(position_dir * tangent_dir, axis=0)
            else:
                position_dir = position_dir / np.linalg.norm(position_dir)
                tangent_dir = tangent_dir / np.linalg.norm(tangent_dir)

                angle_arccos = np.sum(position_dir * tangent_dir)
        return np.arccos(angle_arccos)

    def get_angle_weight(
        self,
        angles,
        max_angle=pi,
        min_angle=0,
        check_range=False,
        weight_pow=1,
    ):
        # TODO: move to utils (?) / angle utils
        n_angles = np.array(angles).shape[0]
        if check_range:
            ind_low = angles <= min_angle
            if np.sum(ind_low):
                return ind_low / np.sum(ind_low)

            angles = np.min(np.vstack((angles, np.ones(n_angles) * max_angle)))

        zero_ind = angles <= min_angle
        if np.sum(zero_ind):
            return zero_ind / np.sum(zero_ind)

        nonzero_ind = angles < max_angle
        if not np.sum(nonzero_ind):
            warnings.warn("No angle has an influence")
            # print('Angles', angles)
            return np.zeros(angles.shape)

        elif np.sum(nonzero_ind) == 1:
            return nonzero_ind * 1.0

        # [min, max] -> [0, 1] weights
        weights = (angles[nonzero_ind] - min_angle) / (max_angle - min_angle)

        # [min, max] -> [infty, 1]
        weights = 1 / weights

        # [min, max] -> [infty, 0]
        weights = (weights - 1) ** weight_pow

        weight_norm = np.sum(weights)

        if weight_norm:
            weights = weights / weight_norm

        weights_all = np.zeros(angles.shape)
        weights_all[nonzero_ind] = weights
        return weights_all

    def get_distance_weight(self, distance, power=1, distance_min=0):
        ind_positiveDistance = distance > 0

        distance = distance - distance_min
        weights = np.zeros(distance.shape)
        weights[ind_positiveDistance] = (1.0 / distance[ind_positiveDistance]) ** power
        weights[ind_positiveDistance] /= np.sum(weights[ind_positiveDistance])
        # weights[~ind_positiveDistance] = 0
        return weights

    def get_outwards_reference_direction(
        self, position: np.ndarray, in_global_frame: bool = False
    ) -> np.ndarray:
        """Returns reference direction pointing away from obstacle.
        At the reference point, a (dummy) vector of length one is returned."""
        return (-1) * self.get_reference_direction(position, in_global_frame)

    def get_reference_direction(
        self, position: np.ndarray, in_global_frame: bool = False
    ) -> np.ndarray:
        """Returns reference direction pointing away from obstacle.
        At the reference point, a (dummy) vector of length one is returned."""
        if in_global_frame:
            ref_dir = self.center_position - position
        else:
            ref_dir = (-1) * position

        # Normal direction
        norm_of_ref = LA.norm(ref_dir)

        if norm_of_ref:
            return ref_dir / norm_of_ref
        else:
            return np.ones(self.dim) / self.dim

    def get_linear_velocity(self, *arg, **kwargs):
        return self.linear_velocity_const

    def get_angular_velocity(self, *arg, **kwargs):
        return self.angular_velocity_const

    def get_scaled_boundary_points(
        self, scale, safety_margin=True, redraw_obstacle=False
    ):
        # Draws at 1:scale
        if safety_margin:
            scaled_boundary_points = scale * self._boundary_points_margin
        else:
            scaled_boundary_points = scale * self._boundary_points

        return self.transform_relative2global(scaled_boundary_points)

    def obs_check_collision(
        self,
    ):
        raise NotImplementedError()

    def get_distance_to_hullEdge(self, position, hull_edge=None):
        raise NotImplementedError()
