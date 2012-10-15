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
  parser.add_option("-r", "--radius", dest="radius",
                    help="maximum distance from sink to initiate a build",
                    default=5.0,
                    type="float")
  parser.add_option("-d", "--density", dest="density",
                    help="minimum distance between planetary defeses",
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

  BuildUpgrades(g, sink, options.radius, options.density)


def BuildUpgrades(g, sink, collection_radius, defense_density):
  has_pd = []
  total = 0

  for p in g.planets:
    p.load()
    if p.has_upgrade('Planetary Defense 1'):
      has_pd.append(p)
    if p.society > 15 and p.can_upgrade('Long Range Sensors 1'):
      if p.start_upgrade('Long Range Sensors 1'):
        print "built LRS at %s." % p.name
        total += 1
    if p.society > 25 and p.can_upgrade('Long Range Sensors 2'):
      if p.start_upgrade('Long Range Sensors 2'):
        print "built LRS2 at %s." % p.name
        total += 1
    if p.society > 30 and p.can_upgrade('Slingshot'):
      if p.start_upgrade('Slingshot'):
        print "built Slingshot at %s." % p.name
        total += 1
    if p.society > 50 and p.can_upgrade('Matter Synth 1'):
      if p.start_upgrade('Matter Synth 1'):
        print "built Matter Synth 1 at %s." % p.name
        total += 1
    if p.can_upgrade('Matter Synth 2'):
      if p.start_upgrade('Matter Synth 2'):
        print "built Matter Synth 2 at %s." % p.name
        total += 1
    if (sink.distance_to(p) <= collection_radius and
        p.can_upgrade('Military Base')):
      if p.start_upgrade('Military Base'):
        print "built Military Base at %s." % p.name
        total += 1

  for p in g.planets:
    if p.can_upgrade('Planetary Defense 1'):
      far_enough = True
      for existing_defense in has_pd:
        far_enough = (far_enough and
                      existing_defense.distance_to(p) >= defense_density)
      if far_enough:
        if p.start_upgrade('Planetary Defense 1'):
          print "built Planetary Defense 1 at %s." % p.name
          total += 1

  print "started %d upgrades" % total


if __name__ == "__main__":
    main()
