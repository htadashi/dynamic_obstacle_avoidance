#!/USSR/bin/python3

'''
Script which creates a variety of examples of local modulation of a vector field with obstacle avoidance. 

@author LukasHuber
@date 2018-02-15
'''

# Command to automatically reload libraries -- in ipython before exectureion
import numpy as np
import matplotlib.pyplot as plt

# Custom libraries
from dynamic_obstacle_avoidance.dynamical_system.dynamical_system_representation import *
from dynamic_obstacle_avoidance.visualization.vector_field_visualization import *  #
from dynamic_obstacle_avoidance.obstacle_avoidance.obstacle import *
from dynamic_obstacle_avoidance.visualization.animated_simulation import run_animation, samplePointsAtBorder

########################################################################
options = [7]

N_resol = 100

saveFigures=True
########################################################################

def main(options=[], N_resol=100, saveFigures=False):
    for option in options:
        obs = [] # create empty obstacle list
        if option==0:
            x_lim = [-1.1,8.1]
            y_lim = [-3.9,6.3]

            xAttractor=[1,0]
            
            obs.append(Cuboid(axes_length=[8, 9.6], center_position=[3, 1], orientation=0./180*pi, absolut_margin=0.0, is_boundary=True))
            
            obs.append(Ellipse(axes_length=[1., 2], center_position=[5, 2.1], p=[1,1], orientation=150./180*pi, sf=1, is_boundary=False))

            obs.append(Ellipse(axes_length=[0.3, 1.8], center_position=[3, -2.4], p=[1,1], orientation=-70./180*pi, sf=1, is_boundary=False))
                                
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=[], xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_initial', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)
            

        if option==1:
            x_lim = [-1.1,8.1]
            y_lim = [-3.9,6.3]

            xAttractor=[1,0]
            
            obs.append(Cuboid(
                axes_length=[8, 9.6],
                center_position=[3, 1],
                orientation=0./180*pi,
                absolut_margin=0.0,
                is_boundary=True))
            
            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_twoEllipses_quiver', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_twoEllipses', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

            
        if option==2:
            x_lim = [-1.1,8.1]
            y_lim = [-3.9,6.1]

            xAttractor=[1,0]
            
            obs.append(Ellipse(axes_length=[3.5, 4.0], center_position=[4, 2.0], p=[1,1], orientation=-70./180*pi, sf=1, is_boundary=True))
            
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryEllipse', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

            
        if option==3:
            x_lim = [-1.1,8.1]
            y_lim = [-3.9,6.1]

            xAttractor=[1,0]
            
            obs.append(Ellipse(axes_length=[3.5, 4.0], center_position=[4, 2.0], p=[1,1], orientation=-70./180*pi, sf=1, is_boundary=True))
            
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryEllipse', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

            
        if option==4:
            x_lim = [-1.1,8.1]
            y_lim = [-3.9,6.3]

            xAttractor=[1,0]
            
            obs.append(Cuboid(axes_length=[3, 3], center_position=[3, 1], orientation=0./180*pi, absolut_margin=0.0, is_boundary=False))
            
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_twoEllipses', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

            
        if option==5:
            x_lim = [-3.1,7.1]
            y_lim = [-3.9,6.3]

            xAttractor=[-1,0.2]

            edge_points = np.array([[1, 4, 2],
                                    [-1, -0.5, 4]])
            
            obs.append(Polygon(edge_points=edge_points, orientation=0./180*pi, absolut_margin=0.0, is_boundary=False))
            
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_triangle', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol)

        if option==6:
            x_lim = [-4.1,7.1]
            y_lim = [-3.9,6.3]

            xAttractor=[-3,3]

            edge_points = np.array([[1.3, 2.3, 2, 0,-2,-2.3,-1.3, 0],
                                    [ -2,   0, 4, 1, 4, 0  ,  -2, -2.2 ]])

            n_points = 5
            points_init = np.vstack((x_lim[1]*np.ones(n_points),
                                     np.linspace(y_lim[0], y_lim[1], n_points)))
            
            obs.append(Polygon(edge_points=edge_points, orientation=0./180*pi, absolut_margin=0.0, is_boundary=False))
            
            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_polygon_concave', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=False, points_init=[])
            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_polygon_concave', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True, points_init=points_init)
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_twoEllipses', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True)

    
        if option==7:
            x_lim = [-2.7, 3.1]
            y_lim = [-2.7, 2.4]
            xAttractor=[-1.5,1.5]

            edge_points = np.array([[1.3, 2.3, 2, 0   ,-2,-2.3,-1, -2.3, 0],  
                                    [ -2,   0, 2, 0.25, 2, 0  , -.5,  - 2, -2.2 ]])


            n_points = 4
            points_init = np.vstack((np.linspace(-1, 2, n_points),
                                     np.linspace(-2, 0, n_points)))
            # points_init = []
                                     
            
            obs.append(Polygon(edge_points=edge_points, orientation=0./180*pi, absolut_margin=0.0, is_boundary=True))

            # run_animation(points_init, obs, x_range=x_lim, y_range=y_lim, dt=0.0001, N_simuMax=600, convergenceMargin=0.3, sleepPeriod=0.01)
            
            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryCuboid_twoEllipses', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=False)
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryPolygon_starshape', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True,points_init=[])
            # fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='linearSystem_boundaryPolygon_starshape_streampoints', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True,points_init=points_init)

        if option==8:
            x_lim = [-4.1, 4.1]
            y_lim = [-4.1, 4.1]
            
            xAttractor=[-3.0, 3.0]

            obs=[]
            obs.append(StarshapedFlower(orientation=00./180*pi))
            
            points_init = []
            
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='flower_shape_normalObstacle', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True, points_init=points_init)
            obs=[]
            obs.append(StarshapedFlower(orientation=30./180*pi))
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='flower_shape_normalObstacle_twisted', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True, points_init=points_init)

        if option==9:
            x_lim = [-4.1, 4.1]
            y_lim = [-4.1, 4.1]
            
            xAttractor=[-3.0, 0.2]

            points_init = []
            
            obs=[]
            obs.append(StarshapedFlower(radius_magnitude=1, radius_mean=3,
                                        orientation=30./180*pi, is_boundary=True,
                                        number_of_edges=5))
            fig_mod, ax_mod = Simulation_vectorFields(x_lim, y_lim,  obs=obs, xAttractor=xAttractor, saveFigure=saveFigures, figName='flower_shape_boundary', noTicks=False, draw_vectorField=True,  automatic_reference_point=False, point_grid=N_resol, show_streamplot=True, points_init=points_init)  



if (__name__==("__main__")):
    if len(sys.argv) > 1:
        options = sys.argv[1]

    if len(sys.argv) > 2:
        N_resol = sys.argv[2]

    if len(sys.argv) > 3:
        saveFigures = sys.argv[3]

    main(options=options, N_resol=N_resol, saveFigures=saveFigures)

    # input("\nPress enter to continue...")

# Run function

