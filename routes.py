#!/usr/bin/python

import game
from optparse import OptionParser
import math
import shape
import sys

parser = OptionParser()
parser.add_option("-U", "--username", dest="username",
                  help="username of login")
parser.add_option("-P", "--password", dest="password",
                  help="password for login")
parser.add_option("-x", "--xcoord", dest="x", 
                  type="float", default = 1645.0,
                  help="center X coordinate")
parser.add_option("-y", "--ycoord", dest="y", 
                  type="float", default = 1470.4,
                  help="center Y coordinate")
parser.add_option("-r", "--radius", dest="r", 
                  type="float", default = 7.0,
                  help="distance from center to corners")
parser.add_option("-p", "--points", dest="p", 
                  type="int", default = 6,
                  help="number of points on the polygon")
parser.add_option("-d", "--degrees", dest="d", 
                  type="int", default = 0,
                  help="degrees of rotation away from point down")
parser.add_option("-X", "--xindex", dest="X", 
                  type="int", default = 0,
                  help="horizontal grid position")
parser.add_option("-Y", "--yindex", dest="Y", 
                  type="int", default = 0,
                  help="vertical grid position")
parser.add_option("-G", "--gutter", dest="G", 
                  type="float", default = 0.1,
                  help="grid gutter width")
parser.add_option("-n", "--name", dest="name", default = 'foo',
                  help="name of the route.")
(options, args) = parser.parse_args()

g = game.Galaxy()
if options.username and options.password:
  # explicit login
  g.login(options.username, options.password, force=True)
else:
  # try to pick up stored credentials
  g.login()

r = options.r
x0 = options.x
y0 = options.y
p = options.p
offset = options.d
name = options.name
X = options.X
Y = options.Y
G  = options.G

if X != 0 or Y != 0:
  # do hexoganl dense-pack, even if they are not hexagons
  inscribed_radius = r * math.cos(math.pi / 6)
  x_step = 2 * inscribed_radius + G
  y_step = x_step * math.sin(math.pi / 3)
  x0 += X * x_step
  y0 += Y * y_step
  if (Y % 2) == 1:
    x0 += x_step / 2
  
points = []
for d in range(0, 360, 360/p):
    radians = math.pi * (float(d + offset) / 180.0)
    x = x0 + r * math.sin(radians)
    y = y0 + r * math.cos(radians)
    points.append((x, y))
route = g.create_route(name, True, *points)
if name == 'foo':
  boundary = shape.Polygon(*(route.points))
  sector = g.load_sectors(boundary.bounding_box())
  route_planets = []
  for p in sector["planets"]["unowned"]:
    if boundary.inside(p.location):
      p.distance_to_center = boundary.distance(p.location)
      route_planets.append(p)
  for p in sector["planets"]["owned"]:
    if boundary.inside(p.location):
      p.distance_to_center = boundary.distance(p.location)
      route_planets.append(p)
  route_planets.sort(key=lambda planet: planet.distance_to_center)
  name = '%s Loop' % route_planets[0].name[:15]
  print 'renaming to: %s' % name
  route.rename(name)

print 'Created route %d, named %s.' % (route.routeid, route.name)
