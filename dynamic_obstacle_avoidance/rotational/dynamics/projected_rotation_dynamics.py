""" Class to Deviate a DS based on an underlying obtacle.
"""
# %%
import sys
import math
import copy
import os
from typing import Optional

# from enum import Enum

import numpy as np
from numpy import linalg as LA
import warnings

from vartools.dynamical_systems import DynamicalSystem
from vartools.linalg import get_orthogonal_basis
from vartools.dynamical_systems import LinearSystem

# from vartools.linalg import get_orthogonal_basis
# from vartools.directional_space import get_angle_space

from dynamic_obstacle_avoidance.obstacles import Obstacle
from dynamic_obstacle_avoidance.obstacles import EllipseWithAxes as Ellipse
from dynamic_obstacle_avoidance.visualization import plot_obstacles

from dynamic_obstacle_avoidance.rotational.rotational_avoidance import (
    obstacle_avoidance_rotational,
)

from dynamic_obstacle_avoidance.rotational.vector_rotation import VectorRotationXd
from dynamic_obstacle_avoidance.rotational.datatypes import Vector


class ProjectedRotationDynamics:
    """
    A dynamical system which locally modulates

    Properties
    ----------
    obstacle: The obstacle around which shape the DS is deformed
    attractor_position: Position of the attractor
    center_direction: The direction of the DS at the center of the obstacle

    (Optional)
    min_gamma (> 1): The position at which the DS has 'maximum' rotation
    max_gamma (> min_gamma): The gamma-distance at which the influence stops.
    """

    # TODO: include Lyapunov function which checks avoidance.
    # this might effect the 'single-saddle point' on the surface'

    def __init__(
        self,
        obstacle: Obstacle,
        attractor_position: np.ndarray,
        reference_velocity: np.ndarray,
        initial_dynamics: Optional[np.ndarray] = None,
        min_gamma: float = 1,
        max_gamma: float = 10,
    ) -> None:
        self.obstacle = obstacle
        self.attractor_position = attractor_position

        self.maximum_velocity = LA.norm(reference_velocity)
        if not self.maximum_velocity:
            raise ValueError("Zero velocity was obtained.")

        reference_velocity = reference_velocity / self.maximum_velocity

        attractor_dir = self.attractor_position - obstacle.center_position
        if not (attr_norm := LA.norm(attractor_dir)):
            warnings.warn("Obstacle is at attractor - zero deviation")
            return

        self.rotation = VectorRotationXd.from_directions(
            vec_init=attractor_dir / attr_norm, vec_rot=reference_velocity
        )
        self.min_gamma = min_gamma
        self.max_gamma = max_gamma
        # Modify if needed
        self.attractor_influence = 3
        self.dotprod_projection_power = 2

        if initial_dynamics is None:
            initial_dynamics = LinearSystem(attractor_position=attractor_position)
        else:
            self.initial_dynamics = initial_dynamics

        # self.base = get_orthogonal_basis()
        # self.deviation = get_angle_space(reference_velocity, null_matrix=self.base)

    def get_projected_gamma(self, position: Vector) -> float:
        # Get gamma
        gamma = self.obstacle.get_gamma(position, in_global_frame=True)
        if gamma >= self.max_gamma:
            return self.gamma_max

        elif gamma >= self.min_gamma:
            # Weight is additionally based on dot-product
            attractor_dir = self.attractor_position - position
            if dist_attractor := LA.norm(attractor_dir):
                attractor_dir = attractor_dir / dist_attractor
                dot_product = np.dot(attractor_dir, self.rotation.base0)
                gamma = gamma ** (2 / (dot_product + 1))

                if dist_obs := LA.norm(self.obstacle.center_position):
                    dist_stretching = LA.norm(position) / LA.norm(
                        self.obstacle.center_position
                    )
                    gamma = gamma**dist_stretching
                else:
                    gamma = self.gamma_max

            else:
                gamma = self.gamma_max

    def _get_deflation_weight(self, gamma: float) -> float:
        return 1.0 / gamma

    def _get_position_after_deflating_obstacle(
        self,
        position: Vector,
        in_obstacle_frame: bool = True,
        deflation_weight: float = 1.0,
    ) -> Vector:
        """Returns position in the environment where the obstacle is shrunk.
        (in the obstacle-frame.)

        Due to the orientation the evaluation should be done in the obstacle frame (!)
        """
        radius = self.obstacle.get_local_radius(
            position, in_global_frame=not (in_obstacle_frame)
        )

        if in_obstacle_frame:
            relative_position = position
        else:
            relative_position = position - self.obstacle.center_position

        pos_norm = LA.norm(relative_position)

        if pos_norm < radius:
            if in_obstacle_frame:
                return np.zeros_like(position)
            else:
                return np.copy(self.obstacle.center_position)

        deflated_position = (
            (pos_norm - radius * deflation_weight) / pos_norm
        ) * relative_position

        if in_obstacle_frame:
            return deflated_position
        else:
            return deflated_position + self.obstacle.center_position

    def _get_position_after_inflating_obstacle(
        self,
        position: Vector,
        in_obstacle_frame: bool = True,
        deflation_weight: float = 1.0,
    ) -> Vector:
        """Returns position in the environment where the obstacle is shrunk.

        Due to the orientation the evaluation should be done in the obstacle frame (!)
        """
        radius = self.obstacle.get_local_radius(
            position, in_global_frame=not (in_obstacle_frame)
        )

        if in_obstacle_frame:
            relative_position = position
        else:
            relative_position = position - self.obstacle.center_position

        if not (pos_norm := LA.norm(relative_position)):
            # Needs a tiny value
            relative_position[0] = 1e6
            pos_norm = relative_position[0]

        inflated_position = (
            (pos_norm + radius * deflation_weight) / pos_norm
        ) * relative_position

        if in_obstacle_frame:
            return inflated_position
        else:
            return inflated_position + self.obstacle.center_position

    def _get_folded_position_opposite_kernel_point(
        self,
        position: Vector,
        attractor_position: Vector,
        in_obstacle_frame: bool = True,
    ) -> Vector:
        """Returns the relative position folded with respect to the dynamics center."""

        # Copy just in case - but probably not needed
        # relative_position = np.copy(relative_position)

        if in_obstacle_frame:
            # If it's in the obstacle-frame => needs to be inverted...
            vec_attractor_to_obstacle = (-1) * attractor_position
        else:
            vec_attractor_to_obstacle = (
                self.obstacle.center_position - attractor_position
            )

        # 'Unfold' the circular plane into an infinite -y/+y-plane
        if not (dist_attr_obs := LA.norm(vec_attractor_to_obstacle)):
            raise NotImplementedError("Implement for position at center.")
        dir_attractor_to_obstacle = vec_attractor_to_obstacle / dist_attr_obs

        # Get values in the attractor frame of reference
        vec_attractor_to_position = position - attractor_position

        basis = get_orthogonal_basis(dir_attractor_to_obstacle)
        transformed_position = basis.T @ vec_attractor_to_position

        # Stretch x-values along x-axis in order to have a x-weight at the attractor
        if dist_attr_pos := LA.norm(vec_attractor_to_position):
            transformed_position[0] = dist_attr_obs * math.log(
                dist_attr_pos / dist_attr_obs
            )

        else:
            transformed_position[0] = (-1) * sys.float_info.max

        dir_attractor_to_position = vec_attractor_to_position / dist_attr_pos
        dot_prod = np.dot(dir_attractor_to_position, dir_attractor_to_obstacle)

        if dot_prod <= -1:
            # Put it very far away in a random direction
            transformed_position[1] = sys.float_info.max

        elif dot_prod < 1:
            if trafo_norm := LA.norm(transformed_position[1:]):
                # Numerical error can lead to zero division, even though it should be excluded
                dotprod_factor = 2 / (1 + dot_prod) - 1
                dotprod_factor = dotprod_factor ** (1.0 / self.dotprod_projection_power)

                transformed_position[1:] = (
                    transformed_position[1:]
                    / LA.norm(transformed_position[1:])
                    * dotprod_factor
                )

        transformed_position = basis @ transformed_position

        return transformed_position

    def _get_unfolded_position_opposite_kernel_point(
        self,
        transformed_position: Vector,
        attractor_position: Vector,
        in_obstacle_frame: bool = True,
    ) -> Vector:
        """Returns UNfolded rleative position folded with respect to the dynamic center.

        Input and output are in the obstacle frame of reference."""
        if not in_obstacle_frame:
            dir_attractor_to_obstacle = (
                self.obstacle.center_position - attractor_position
            )
        else:
            dir_attractor_to_obstacle = (-1) * attractor_position

        if not (dist_attr_obs := LA.norm(dir_attractor_to_obstacle)):
            raise NotImplementedError()

        dir_attractor_to_obstacle = dir_attractor_to_obstacle / dist_attr_obs

        # Everything with resepect to attractor

        # Dot product is sufficient, as we only need first element.
        # Rotation is performed with VectorRotationXd
        vec_attractor_to_position = transformed_position - attractor_position
        radius = np.dot(dir_attractor_to_obstacle, vec_attractor_to_position)

        # Ensure that the square root stays positive close to singularities
        transform_norm = LA.norm(vec_attractor_to_position)
        dot_prod = math.sqrt(max(transform_norm**2 - radius**2, 0))
        dot_prod = dot_prod**self.dotprod_projection_power
        dot_prod = 2.0 / (dot_prod + 1) - 1

        if dot_prod < 1:
            dir_perp = (
                dir_attractor_to_obstacle
                - vec_attractor_to_position / transform_norm * dot_prod
            )

            rotation_ = VectorRotationXd.from_directions(
                vec_init=dir_attractor_to_obstacle,
                vec_rot=dir_perp / LA.norm(dir_perp),
            )
            rotation_.rotation_angle = math.acos(dot_prod)

            # Initially a unit vector
            relative_position = rotation_.rotate(dir_attractor_to_obstacle)
        else:
            relative_position = dir_attractor_to_obstacle

        relative_position = (
            relative_position
            * math.exp((radius - dist_attr_obs) / dist_attr_obs)
            * dist_attr_obs
        )

        # Move out-of from attractor-frame
        relative_position = relative_position + attractor_position

        # if in_obstacle_frame:
        #     relative_position = self.obstacle.base.transform_position_from_relative(
        #         relative_position
        #     )

        # Simplified transform (without rotation), since everything was in obstacle frame
        if in_obstacle_frame:
            relative_position = relative_position + self.obstacle.pose.position

        return relative_position

    def get_projected_position(self, position: Vector) -> Vector:
        """Projected point in 'linearized' environment

        Assumption of the point being outside of the obstacle."""

        # Do the evaluation in local frame
        relative_position = self.obstacle.pose.transform_position_to_relative(position)
        relative_attractor = self.obstacle.pose.transform_position_to_relative(
            self.attractor_position
        )

        gamma = self.obstacle.get_gamma(relative_position, in_obstacle_frame=True)
        weight = self._get_deflation_weight(gamma)

        if not (pos_norm := LA.norm(relative_position)):
            raise NotImplementedError()

        # Shrunk position
        relative_position = self._get_position_after_deflating_obstacle(
            relative_position, in_obstacle_frame=True, deflation_weight=weight
        )
        relative_attractor = self._get_position_after_deflating_obstacle(
            relative_attractor, in_obstacle_frame=True, deflation_weight=weight
        )

        relative_position = self._get_folded_position_opposite_kernel_point(
            relative_position, relative_attractor, in_obstacle_frame=True
        )

        relative_position = self._get_position_after_inflating_obstacle(
            relative_position, in_obstacle_frame=True, deflation_weight=weight
        )

        return self.obstacle.pose.transform_position_from_relative(relative_position)

    def _get_lyapunov_gradient(self, position: Vector) -> Vector:
        """Returns the Gradient of the Lyapunov function.
        For now, we assume a quadratic Lyapunov function."""
        # Weight is additionally based on dot-product
        attractor_dir = self.attractor_position - position
        if not (dist_attractor := LA.norm(attractor_dir)):
            return np.zeros_like(position)

        attractor_dir = attractor_dir / dist_attractor
        return attractor_dir

    def _get_projected_lyapunov_gradient(self, position: Vector) -> Vector:
        """Returns projected lyapunov gradient function.

        It is assumed that z-axis is the base gradient."""
        attractor_dir = self.attractor_position - self.obstacle.center_position

        if not (dist_attractor := LA.norm(attractor_dir)):
            return np.zeros_like(attractor_dir)

        return attractor_dir / dist_attractor

    def _get_vector_rotation_of_modulation(
        self, position: Vector, velocity: Vector
    ) -> VectorRotationXd:
        """Returns the rotation of the modulation close to an obstacle."""
        if not (vel_norm := LA.norm(velocity)):
            return VectorRotationXd(np.eye(self.dimension, 2), rotation_angle=0.0)

        modulated_velocity = obstacle_avoidance_rotational(
            position,
            velocity,
            obstacle_list=[self.obstacle],
            convergence_velocity=velocity,
        )
        if not (mod_vel_norm := LA.norm(modulated_velocity)):
            return VectorRotationXd(np.eye(self.dimension, 2), rotation_angle=0.0)

        return VectorRotationXd.from_directions(
            velocity / vel_norm, modulated_velocity / mod_vel_norm
        )

    def get_base_reference(self, position: Vector) -> Vector:
        # This should be either +/- attractor-position
        dist_attr = self.attractor_position - position
        return dist_attr / LA.norm(dist_attr)

    def get_single_obstacle_convergence_rotation(
        self,
        position: Vector,
        obstacle: Obstacle,
    ) -> Vector:
        """Returns"""

        initial_velocity = self.initial_dynamcis.evaluate(position)
        obstacle_velocity = self.initial_dynaics.evaluate(obstacle.center_position)

        base_convergence_direction = self.get_base_reference(position)

        rotation_conv_to_obs_vel = VectorRotationXd.from_directions(
            base_convergence_direction, obstacle_velocity
        )

        dir_pos_to_attractor = self.initial_velocity - self.attractor_position
        if not (dir_norm := LA.norm(dir_pos_to_attractor)):
            # We're at the attractor -> no / zero velocity
            return np.zeros_like(position)

        dir_pos_to_obstacle = self.obstacle.center_position - self.attractor_position
        if not (obs_norm := LA.norm(dir_pos_to_obstacle)):
            raise NotImplementedError()

        rotation_pos_to_pos_transform = VectorRotationXd.from_directions(
            dir_pos_to_attractor, dir_pos_to_obstacle
        )

        if rotation_pos_to_pos_transform.rotation_angle >= math.pi:
            # We're the maximum away in the projected space, no linearization
            return initial_velocity

        initial_velocity_transformed = rotation_pos_to_pos_transform.rotat(
            initial_velocity
        )

        # Rotate
        projected_position = self.get_projected_position(position)
        proj_gamma = obstacle.get_gamma(projected_position, in_global_frame=True)
        weight = min(1, 1 / proj_gamma)

        # TODO: use VectorRotationXd for this...
        averaged_direction_transformed = directional_weighted_sum(
            null_direction=base_convergence_direction,
            directions=np.vstack((obstacle_velocity, initial_velocity_transformed)).T,
            weights=[weight, 1 - weight],
        )

        averaged_direction = rotation_pos_to_pos_transform.rotate(
            averaged_direction_transformed, rot_factor=-1
        )

        return averaged_direction

    def _get_all_obstacle_convergence(self):
        pass
