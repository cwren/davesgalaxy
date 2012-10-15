#!/usr/bin/env python

import game
from optparse import OptionParser
import sys


def main():
  parser = OptionParser()
  parser.add_option("-U", "--username", dest="username",
                    help="username of login")
  parser.add_option("-P", "--password", dest="password",
                    help="password for login")
  parser.add_option("-t", "--type", dest="type",
                    help="type of ship to build", default="destroyers")
  parser.add_option("-r", "--radius", dest="radius",
                    help="maximum distance from sink to initiate a build",
                    default=5.0,
                    type="float")
  (options, args) = parser.parse_args()
  
  sink_opt = args[0]
  
  g=game.Galaxy()
  if options.username and options.password:
    # explicit login
    g.login(options.username, options.password, force=True)
  else:
    # try to pick up stored credentials
    g.login()

  try:
    sink = g.get_planet(int(sink_opt))
  except ValueError:
    sink = g.find_planet(sink_opt)
  sink.load()
  print "using planet %d with name %s" % (sink.planetid, sink.name)

  collectsteel(g, sink, options.radius, options.type)


def collectsteel(g, sink, radius, type):  
  total = 0
  
  print 'Looking for planets with excess steel within %f of %s.' % (
    radius, sink.name)
  for p in g.planets:
    if p.planetid != sink.planetid and sink.distance_to(p) <= radius:
      p.load()
      surplus = 1
      while p.can_build({type: surplus}):
        surplus += 1
      surplus -= 1
      if surplus > 0:
        fleet = p.build_fleet({type: surplus},
                              interactive=False,
                              skip_check=True)
        if fleet:
          total += surplus
          fleet.move_to_planet(sink)
        else:
          print "build failed."
          
  
  value = game.ship_cost({type: total})
  print "collected %d steel" % value['steel']

if __name__ == "__main__":
    main()
