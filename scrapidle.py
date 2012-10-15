#!/usr/bin/env python

import game
from optparse import OptionParser
import sys
import types


def dictstr(d):
  return "(" + " ".join(
    "%s=%s" % (str(k),str(v)) for (k,v) in d.items()) + ")"


def main():
  parser = OptionParser()
  parser.add_option("-U", "--username", dest="username",
                    help="username of login")
  parser.add_option("-P", "--password", dest="password",
                    help="password for login")
  parser.add_option("-t", "--type", dest="type",
                    help="type of ship to build", default="destroyers")
  (options, args) = parser.parse_args()
  
  g=game.Galaxy()
  if options.username and options.password:
    # explicit login
    g.login(options.username, options.password, force=True)
  else:
    # try to pick up stored credentials
    g.login()
  
  sink_opt = args[0]
  try:
    sink = g.get_planet(int(sink_opt))
  except ValueError:
    sink = g.find_planet(sink_opt)
  print "using planet %d with name %s" % (sink.planetid, sink.name)

  scrapidle(g, sink, options.type)

def scrapidle(g, sink, type):
  sink.load()
  steel = sink.steel[0]
  print 'Looking for mule fleets of type %s at %s.' % (
    type, sink.name)
  for f in g.fleets:
    if f.at(sink):
      f.load()
      if type in f.ships and len(f.ships.keys()) == 1:
        sink.scrap_fleet(f)
  print "recovered %d steel" % (sink.steel[0] -  steel)
  
  
if __name__ == "__main__":
    main()
