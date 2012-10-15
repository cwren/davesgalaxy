#!/usr/bin/env python
# vim: set ts=2 sw=2 expandtab:

import game
from optparse import OptionParser
import sys
import shape

def main():
  parser = OptionParser()
  parser.add_option("-U", "--username", dest="username",
                    help="username of login")
  parser.add_option("-P", "--password", dest="password",
                    help="password for login")
  parser.add_option("-n", "--noupgrade", dest="doupgrade",
                    action="store_false", default=True, help="dry run")
  parser.add_option("-m", "--maxarcs", dest="maxarcs",
                    action="store", type="int", default=-1, help="maximum arcs to build")
  parser.add_option("-p", "--perplanet", dest="perplanet",
                    action="store", type="int", default=-1, help="max arcs per planet")
  parser.add_option("-l", "--leave", dest="leave",
                    action="store", type="int", default=0, help="min of arcs to leave on planet")

  parser.add_option("-x", "--sx", dest="sx",
                    action="store", type="float", help="source x coordinate")
  parser.add_option("-y", "--sy", dest="sy",
                    action="store", type="float", help="source y coordinate")
  parser.add_option("-r", "--sr", dest="sr",
                    action="store", type="float", default=20.0, help="builder radius to consider")

  parser.add_option("-X", "--tx", dest="tx",
                    action="store", type="float", help="target x coordinate")
  parser.add_option("-Y", "--ty", dest="ty",
                    action="store", type="float", help="target y coordinate")
  parser.add_option("-R", "--tr", dest="tr",
                    action="store", type="float", help="target radius to consider")

  parser.add_option("-s", "--source_route", dest="source",
                    type="string", help="route enclosing source")
  parser.add_option("-S", "--sink_route", dest="sink",
                    type="string", help="route enclosing sink")

  (options, args) = parser.parse_args()

  if (options.sx == None or options.sy == None) and options.source == None:
    print "not enough arguments"
    parser.print_help()
    sys.exit(1)

  # if they didn't set tx/ty/tr, copy from sx/sy/sr
  if options.tx == None: options.tx = options.sx
  if options.ty == None: options.ty = options.sy
  if options.tr == None: options.tr = options.sr
  if options.sink == None: options.sink = options.source

  print "options " + str(options)

  g=game.Galaxy()
  if options.username and options.password:
    # explicit login
    g.login(options.username, options.password, force=True)
  else:
    # try to pick up stored credentials
    g.login()
    
  sink_shape = None
  if options.sink != None:
    sink_route = g.find_route(options.sink)
    sink_shape = shape.Polygon(*(sink_route.points))
  else:
    sink_shape = shape.Circle([options.tx, options.ty], options.tr)

  source_shape = None
  if options.source != None:
    source_route = g.find_route(options.source)
    source_shape = shape.Polygon(*(source_route.points))
  else:
    source_shape = shape.Circle([options.sx, options.sy], options.sr)

  BuildArcs(g, options.doupgrade, options.maxarcs,
            options.perplanet, options.leave,
            source_shape, sink_shape)

def BuildArcs(g, doupgrade, maxarcs, perplanet, leave, source, sink,
              escort=True):
  manifest = { 'arcs': 1 }
  if escort:
    manifest['frigates'] = 1

  # find a list of potential arc builders
  print "looking for arc builders..."
  total_arcs = 0
  arc_builders = []
  for p in g.planets:
    if source.inside(p.location):
      p.load()
      count = p.how_many_can_build(manifest)
      if count and p.society > 30 and p.population > 20000:
        print "planet " + str(p) + " can build " + str(count) + " arcs"
        p.distance_to_target = sink.distance(p.location)
        arc_builders.append(p)
        total_arcs += count

  # sort arc builders by distance to target
  arc_builders = sorted(arc_builders, key=lambda planet: planet.distance_to_target)

  print "found " + str(len(arc_builders)) + " arc building planets capable of building " + str(total_arcs) + " arcs"

  # load the sectors around the target point
  print "looking for unowned planets at target location..."
  sect = g.load_sectors(sink.bounding_box())
  #print sect
  unowned_targets = sect["planets"]["unowned"]

  # trim planets to ones strictly within the radius specified
  foo = []
  for p in unowned_targets:
    if sink.inside(p.location):
      foo.append(p)
  unowned_targets = foo

  print "found " + str(len(unowned_targets)) + " unowned planets"
  
  # trim the list of targets to ones that dont have an arc already incoming
  # 
  print "trimming list of unowned planets..."
  for f in g.fleets:
    f.load()
    try:
      if f.disposition == "Colonize":
      # look for destinations in the NAME-NUMBER form
        pnum = int(f.destination.split('-')[1])
        for p in unowned_targets:
          if p.planetid == pnum:
            print "fleet " + str(f) + " already heading for dest"
            unowned_targets.remove(p)
            break
    except:
      pass

  print "now have " + str(len(unowned_targets)) + " unowned planets"

  # build arcs
  built = 0
  if len(unowned_targets) > 0:
    print "building arcs..."
    arc = manifest
    done = False
    for p in arc_builders:
      if done:
        break

      # trim the number we can build by per-planet limit
      count = p.how_many_can_build(arc);
      if perplanet > 0 and count > perplanet:
        count = perplanet

      # trim the number we can build by the min left limit
      count -= leave
      if count <= 0:
        continue

      # for this builder, find the closest unowned planets
      for t in unowned_targets:
        t.distance_to_target = game.distance_between(p.location, t.location)
      unowned_targets = sorted(unowned_targets, key=lambda planet: planet.distance_to_target)

      print "planet " + str(p) + " can build " + str(count) + " arcs"
      while not done and count > 0 and p.can_build(arc):
          t = unowned_targets[0]
          print "looking to build to " + str(t) + " distance: " + str(t.distance_to_target)
          if doupgrade:
            fleet = p.build_fleet(arc)
            if fleet:
              fleet.move_to_planet(t)
            else:
              print " failed to build fleet"
              count = 0
              break
          
          # cull this target from the list
          unowned_targets.remove(t)
          built += 1 
          count -= 1
          maxarcs -= 1
          if (maxarcs == 0):
            done = True
          if len(unowned_targets) == 0:
            done = True

  if built > 0:
    if doupgrade:
      print "built %d arcs" % built
    else:
      print "would have built %d arcs" % built

  g.write_planet_cache()
  g.write_fleet_cache()

if __name__ == "__main__":
    main()
