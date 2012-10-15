# vim: set ts=2 sw=2 expandtab:
import cookielib
import json
import math
import os
import pickle
import re
import subprocess
import shape
import sys
import time
import types
import urllib
import urllib2
from itertools import izip
from BeautifulSoup import BeautifulSoup

HOST = "http://davesgalaxy.com/"
URL_LOGIN = HOST + "/login/"
URL_VIEW = HOST + "/view/"
URL_PLANETS = HOST + "/planets/list/all/%d/"
URL_FLEETS = HOST + "/fleets/list/all/%d/"
URL_PLANET_DETAIL = HOST + "/planets/%d/info/"
URL_PLANET_UPGRADES =  HOST + "/planets/%d/upgradelist/"
URL_PLANET_UPGRADE_ACTION =  HOST + "/planets/%d/upgrades/%s/%d/"
URL_PLANET_MANAGE = HOST + "/planets/%d/manage/"
URL_PLANET_BUDGET = HOST + "/planets/%d/budget/"
URL_FLEET_DETAIL = HOST + "/fleets/%d/info/"
URL_MOVE_TO_PLANET = HOST + "/fleets/%d/movetoplanet/"
URL_MOVE_TO_ROUTE = HOST + "/fleets/%d/onto/"
URL_MOVE_ROUTE_TO = HOST + "/fleets/%d/routeto/"
URL_BUILD_FLEET = HOST + "/planets/%d/buildfleet/"
URL_SCRAP_FLEET = HOST + "/fleets/%d/scrap/"
URL_BUILD_ROUTE = HOST + '/routes/named/add/'
URL_RENAME_ROUTE = HOST + '/routes/%d/rename/'
URL_SECTORS = HOST + "sectors/"

UPGRADE_UNAVAILABLE = 0
UPGRADE_AVAILABLE = 1
UPGRADE_INACTIVE = 2
UPGRADE_STARTED = 3
UPGRADE_STARTED_0 = 4
UPGRADE_ACTIVE = 5

CACHE_STALE_TIME = 5 * 60 * 60
PLANET_CACHE_FILE = 'planet.dat'
FLEET_CACHE_FILE = 'fleet.dat'
CREDENTIAL_CACHE_FILE = 'login.dat'

ALL_SHIPS = {
  'superbattleships': {'steel':8000,
                       'unobtanium':102,
                       'population':150,
                       'food':300,
                       'antimatter':1050,
                       'money':74917,
                       'krellmetal':290,
                       'needbase':True},
  'bulkfreighters': {'steel':2500,
                     'unobtanium':0,
                     'population':20,
                     'food':20,
                     'antimatter':50,
                     'money':6498,
                     'krellmetal':0,
                     'needbase':False},
  'subspacers': {'steel':625,
                 'unobtanium':0,
                 'population':50,
                 'food':50,
                 'antimatter':250,
                 'money':12486,
                 'krellmetal':16,
                 'needbase':False},
  'arcs': {'steel':10000,
           'unobtanium':0,
           'population':2000,
           'food':1000,
           'antimatter':500,
           'money':9989,
           'krellmetal':0,
           'needbase':False},
  'blackbirds': {'steel':500,
                 'unobtanium':25,
                 'population':5,
                 'food':5,
                 'antimatter':125,
                 'money':9989,
                 'krellmetal':50,
                 'needbase':False},
  'merchantmen': {'steel':750,
                  'unobtanium':0,
                  'population':20,
                  'food':20,
                  'antimatter':50,
                  'money':5998,
                  'krellmetal':0,
                  'needbase':False},
  'scouts': {'steel':250,
             'unobtanium':0,
             'population':5,
             'food':5,
             'antimatter':25,
             'money':249,
             'krellmetal':0,
             'needbase':False},
  'battleships': {'steel':4000,
                  'unobtanium':20,
                  'population':110,
                  'food':200,
                  'antimatter':655,
                  'money':24972,
                  'krellmetal':155,
                  'needbase':True},
  'destroyers': {'steel':1200,
                 'unobtanium':0,
                 'population':60,
                 'food':70,
                 'antimatter':276,
                 'money':5014,
                 'krellmetal':0,
                 'needbase':False},
  'frigates': {'steel':950,
               'unobtanium':0,
               'population':50,
               'food':50,
               'antimatter':200,
               'money':1248,
               'krellmetal':0,
               'needbase':False},
  'cruisers': {'steel':1625,
               'unobtanium':0,
               'population':80,
               'food':100,
               'antimatter':385,
               'money':14983,
               'krellmetal':67,
               'needbase':True},
  'harvesters': {'steel':5000,
               'unobtanium':0,
               'population':25,
               'food':20,
               'antimatter':50,
               'money':6492,
               'krellmetal':0,
               'needbase':True},
}

UPGRADES = [
  'Long Range Sensors 1',
  'Long Range Sensors 2',
  'Trade Incentives',
  'Regional Government',
  'Mind Control',
  'Matter Synth 1',
  'Matter Synth 2',
  'Military Base',
  'Slingshot',
  'Farm Subsidies',
  'Drilling Subsidies',
  'Planetary Defense 1',
  'Petrochemical Power Plant',
  'Fusion Power Plant',
  'Antimatter Power Plant'
]

ME = 'me'

def pairs(t):
  return izip(*[iter(t)]*2)

def parse_coords(s):
  m = re.match(r'\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)', s)
  if m: return map(float, m.groups())
  return None

def ship_cost(manifest):
  cost = {'money': 0,
          'steel': 0,
          'population': 0,
          'unobtanium': 0,
          'food': 0,
          'antimatter': 0,
          'krellmetal': 0,
          'needbase': False}
  for type,quantity in manifest.items():
    cost['money'] += quantity * ALL_SHIPS[type]['money']
    cost['steel'] += quantity * ALL_SHIPS[type]['steel']
    cost['population'] += quantity * ALL_SHIPS[type]['population']
    cost['unobtanium'] += quantity * ALL_SHIPS[type]['unobtanium']
    cost['food'] += quantity * ALL_SHIPS[type]['food']
    cost['antimatter'] += quantity * ALL_SHIPS[type]['antimatter']
    cost['krellmetal'] += quantity * ALL_SHIPS[type]['krellmetal']

    # if one of the ships on the list needs a military base, mark it
    if ALL_SHIPS[type]['needbase']:
      cost['needbase'] = True
  return cost

def distance_between(locationA, locationB):
    return math.sqrt(math.pow(abs(locationA[0]-locationB[0]), 2) +
                     math.pow(abs(locationA[1]-locationB[1]), 2))

class Planet:
  def __init__(self, galaxy, planetid, name='unknown', location=None, owner=ME):
    self.galaxy = galaxy
    self.planetid = int(planetid)
    self.owner = str(owner)
    self.name = str(name)
    self.location = location
    self._loaded = False
    self._upgrades = None
  def __repr__(self):
    return "<Planet #%d \"%s\">" % (self.planetid, self.name)
  def __getstate__(self): 
    return dict(filter(lambda x:  x[0] != 'galaxy',  self.__dict__.items()))
  def load(self, force=False):
    if not force and self._loaded: return False
    retrycount = 0
    while retrycount < 5:
      retrycount = retrycount + 1
      try:
        req = self.galaxy.opener.open(URL_PLANET_DETAIL % self.planetid)
        retrycount = retrycount + 5
      except urllib2.URLError:
        print "url error, retrying"
        pass

    soup = BeautifulSoup(json.load(req)['tab'])

    self.society = int(soup('div',{'class':'info1'})[0]('div')[2].string)
    data = [x.string.strip() for x in soup('td',{'class':'planetinfo2'})]
    i = 0
    if self.name == 'unknown':
      self.name = str(data[i])
    i+=1
    self.owner=data[i]; i+=1
    if self.location == None:
      self.location=map(float, re.findall(r'[0-9.]+', data[i])); 
    i+=1
    if soup.find(text='Distance to Capital:'):
      self.distance=float(data[i]) ; i+=1
    else:
      self.distance=0.0
    if soup.find(text='Income Tax Rate:'):
      self.tax=float(data[i]) ; i+=1
    else:
      self.tax=0.0
    if soup.find(text='Open Ship Yard:'): i+=1
    if soup.find(text='Trades Rare Commodities:'): i+=1
    if soup.find(text='Open Trading:'): i+=1
    if soup.find(text='Tariff Rate:'):
      self.tarif=float(data[i]) ; i+=1
    else:
      self.tarif=0.0
    try:
      self.population=int(data[i]) ; i+=1
      self.money=int(data[i].split()[0]) ; i+=1
      self.steel=map(int, data[i:i+3]) ; i+=3
      self.unobtanium=map(int, data[i:i+3]) ; i+=3
      self.strageness=map(int, data[i:i+3]) ; i+=3
      self.food=map(int, data[i:i+3]) ; i+=3
      self.antimatter=map(int, data[i:i+3]) ; i+=3
      self.consumergoods=map(int, data[i:i+3]) ; i+=3
      self.charm=map(int, data[i:i+3]) ; i+=3
      self.helium3=map(int, data[i:i+3]) ; i+=3
      self.hydrocarbon=map(int, data[i:i+3]) ; i+=3
      self.krellmetal=map(int, data[i:i+3]) ; i+=3
    except IndexError:
      sys.stderr.write("loaded alien planet\n")
    self.loadUpgrades()
    self._loaded = True
    return True
  def how_many_can_build(self, manifest):
    self.load()
    cost = ship_cost(manifest)
    count = -1

    has_base = self.has_active_upgrade('Military Base')
    if cost['needbase'] and not has_base:
      return 0

    if cost['money'] > 0:
      newcount = self.money / cost['money']
      if (count < 0 or newcount < count): count = newcount
    if cost['steel'] > 0:
      newcount = self.steel[0] / cost['steel']
      if (count < 0 or newcount < count): count = newcount
    if cost['population'] > 0:
      newcount = self.population / cost['population']
      if (count < 0 or newcount < count): count = newcount
    if cost['unobtanium'] > 0:
      newcount = self.unobtanium[0] / cost['unobtanium']
      if (count < 0 or newcount < count): count = newcount
    if cost['food'] > 0:
      newcount = self.food[0] / cost['food']
      if (count < 0 or newcount < count): count = newcount
    if cost['antimatter'] > 0:
      newcount = self.antimatter[0] / cost['antimatter']
      if (count < 0 or newcount < count): count = newcount
    if cost['krellmetal'] > 0:
      newcount = self.krellmetal[0] / cost['krellmetal']
      if (count < 0 or newcount < count): count = newcount

    if (count < 0): count = 0
    return count
  def can_build(self, manifest):
    return self.how_many_can_build(manifest) > 0
  def build_fleet(self, manifest, interactive=False, skip_check=False):
    fleet = None
    if skip_check or self.can_build(manifest):
      formdata = {}
      formdata['submit-build-%d' % self.planetid] = 1
      formdata['submit-build-another-%d' % self.planetid] =1
      for type,quantity in manifest.items():
        formdata['num-%s' % type] = quantity
      req = self.galaxy.opener.open(URL_BUILD_FLEET % self.planetid,
                                    urllib.urlencode(formdata))
      response = req.read()
      if 'Fleet Built' in response: 
        j = json.loads(response)
        fleet = Fleet(self.galaxy,
                      j['newfleet']['i'],
                      [j['newfleet']['x'], j['newfleet']['y']],
                      True) # feets are created at planets
        if self.galaxy._fleets:
          self.galaxy.fleets.append(fleet)
        if self._loaded:
          cost = ship_cost(manifest)
          self.money -= cost['money']
          self.steel[0] -= cost['steel']
          self.population -= cost['population']
          self.unobtanium[0] -= cost['unobtanium']
          self.food[0] -= cost['food']
          self.antimatter[0] -= cost['antimatter']
          self.krellmetal[0] -= cost['krellmetal']
        if interactive:
          js = 'javascript:handleserverresponse(%s);' % response
          subprocess.call(['osascript', 'EvalJavascript.scpt', js ])
      else:
        sys.stderr.write('error when building: %s' % response)
    else:
      sys.stderr.write('cannot build %s\n' % str(manifest))
    return fleet
  def scrap_fleet(self, fleet):
    if fleet.scrap() and self._loaded and fleet._loaded:
      value = ship_cost(fleet.ships)
      self.money += value['money']
      self.steel[0] += value['steel']
      self.population += value['population']
      self.unobtanium[0] += value['unobtanium']
      self.food[0] += value['food']
      self.antimatter[0] += value['antimatter']
      self.krellmetal[0] += value['krellmetal']
      return value
    else:
      return None
  def view(self):
    js = 'javascript:gm.centermap(%d, %d);' % (self.location[0],
                                               self.location[1])
    subprocess.call(['osascript', 'EvalJavascript.scpt', js ])
  def distance_to(self, other):
    return distance_between(self.location, other.location)
  def loadUpgrades(self):
    if self._upgrades: return self._upgrades
    self._upgrades = map(lambda x: UPGRADE_UNAVAILABLE, range(0,len(UPGRADES)))
    try:
      req = self.galaxy.opener.open(URL_PLANET_UPGRADES % self.planetid)
      soup = BeautifulSoup(json.load(req)['tab'])
      for row in soup('tr')[1:]:
        if 'td' in str(row):
          cells=row('td')
          if len(cells) > 3:
            m=re.search(r'/planets/[0-9]+/upgrades/([a-z]+)/([0-9]+).',
                        str(row))
            idx = int(m.group(2))
            self._upgrades[idx] = UPGRADE_AVAILABLE
            if m.group(1) == 'scrap':
              self._upgrades[idx] = UPGRADE_STARTED
              if 'Active' in str(cells[2]):
                self._upgrades[idx] = UPGRADE_ACTIVE
              elif '100%' in str(cells[3]):
                self._upgrades[idx] = UPGRADE_INACTIVE
              elif '0%' in str(cells[3]):
                self._upgrades[idx] = UPGRADE_STARTED_0
    except urllib2.HTTPError:
      sys.stderr.write('failed to read upgrades for planet %d/n' %
                       self.planetid)
    return self._upgrades
  @property
  def upgrades(self):
    if self._upgrades: return self._upgrades
    self.loadUpgrades()
    return self._upgrades
  def can_upgrade(self, upgrade):
    self.loadUpgrades()
    index = UPGRADES.index(upgrade)
    return self.upgrades[index] == UPGRADE_AVAILABLE
  def has_upgrade(self, upgrade):
    self.loadUpgrades()
    index = UPGRADES.index(upgrade)
    return self.upgrades[index] > UPGRADE_AVAILABLE
  def has_active_upgrade(self, upgrade):
    self.loadUpgrades()
    index = UPGRADES.index(upgrade)
    return self.upgrades[index] == UPGRADE_ACTIVE
  def building_upgrade_zeropercent(self, upgrade):
    self.loadUpgrades()
    index = UPGRADES.index(upgrade)
    return self.upgrades[index] == UPGRADE_STARTED_0
  def building_upgrade(self, upgrade):
    self.loadUpgrades()
    index = UPGRADES.index(upgrade)
    return self.upgrades[index] == UPGRADE_STARTED or self.upgrades[index] == UPGRADE_STARTED_0
  def start_upgrade(self, upgrade):
    index = UPGRADES.index(upgrade)
    if not self.can_upgrade(upgrade):
      return False

    try:
      self.galaxy.opener.open(URL_PLANET_UPGRADE_ACTION %
                              (self.planetid, 'start', index))
      self.upgrades[index] = UPGRADE_STARTED_0
      return True
    except urllib2.HTTPError:
      return False
  def scrap_upgrade(self, upgrade):
    index = UPGRADES.index(upgrade)
    try:
      self.galaxy.opener.open(URL_PLANET_UPGRADE_ACTION %
                              (self.planetid, 'scrap', index))
      self.upgrades[index] = UPGRADE_AVAILABLE
      return True
    except urllib2.HTTPError:
      return False

class Fleet:
  def __init__(self, galaxy, fleetid, coords, at=False):
    self.galaxy = galaxy
    self.fleetid = int(fleetid)
    self.coords = coords
    self.at_planet = at
    self.home = None
    self.disposition = None
    self._loaded = False
  def __repr__(self):
    return "<Fleet #%d%s @ (%.1f,%.1f)>" % (self.fleetid, 
      (' (%s, %d ships)' % (self.disposition, len(self.ships))) \
        if self._loaded else '',
      self.coords[0], self.coords[1])
  def __getstate__(self): 
    return dict(filter(lambda x:  x[0] != 'galaxy',  self.__dict__.items()))
  def load(self, force=False):
    if not force and self._loaded: return False
    try:
      req = self.galaxy.opener.open(URL_FLEET_DETAIL % self.fleetid)
      soup = BeautifulSoup(json.load(req)['pagedata'])
      home = str(soup.find(text="Home Port:").findNext('td').string)
      self.home = self.galaxy.find_planet(int(home.split('-')[1]))
      dest = str(soup.find(text="Destination:").findNext('td').string)
      self.destination = parse_coords(dest)
      if not self.destination:
        dsplit = dest.split('-')
        self.destination = self.galaxy.find_planet(int(dsplit[len(dsplit)-1]))
        if not self.destination:
          # must be headed for a unowned planet
          self.destination = dest
      self.disposition = str(soup.find(text="Disposition:")
                             .findNext('td').string).split(' - ')[1]
      try:
        self.speed = float(soup.find(text="Current Speed:")
                           .findNext('td').string)
      except: self.speed = 0
      self.ships = dict()
      try:
        for k,v in pairs(soup('h3')[0].findAllNext('td')):
          shiptype = re.match(r'[a-z]+', k.string).group()
          if not shiptype in ALL_SHIPS.keys(): continue
          self.ships[shiptype] = int(v.string)
      except IndexError:
        pass  # emply fleet
    except IndexError:
      # stale fleet
      self.destination = None
      self.disposition = "unknown"
      self.speed = 0.0
      self.ships = dict()
    except urllib2.HTTPError:
      # stale fleet
      self.destination = None
      self.disposition = "unknown"
      self.speed = 0.0
      self.ships = dict()
    self._loaded = True
    return True
  def move_to_planet(self, planet):
    formdata = {}
    formdata['planet' ] = planet.planetid
    req = self.galaxy.opener.open(URL_MOVE_TO_PLANET % self.fleetid,
                                  urllib.urlencode(formdata))
    response = req.read()
    success = 'Destination Changed' in response
    if not success:
      sys.stderr.write('%s/n' % response)
    return success
  def move_to_route(self, route, insertion_point=None):
    formdata = {}
    formdata['route' ] = route.routeid
    if insertion_point == None:
      route_shape = shape.Polygon(*(route.points))
      insertion_point = route_shape.nearest_to(self.coords)
    formdata['sx'] = insertion_point[0]
    formdata['sy'] = insertion_point[1]
    req = self.galaxy.opener.open(URL_MOVE_TO_ROUTE % self.fleetid,
                                  urllib.urlencode(formdata))
    response = req.read()
    success = 'Fleet Routed' in response
    if not success:
      sys.stderr.write('%s/n' % response)
    return success
  def route_to(self, points, planetid=None):
    formdata = {}
    formdata['circular'] = False
    formdata['route'] = ','.join(map(lambda p: 
                                     '/'.join(map(lambda x: str(x), p)), 
                                     points))
    if planetid:
      formdata['route'] = "%s, %s" % (formdata['route'], str(planetid))
    req = self.galaxy.opener.open(URL_MOVE_ROUTE_TO % self.fleetid,
                                  urllib.urlencode(formdata))
    response = req.read()
    success = 'Fleet Routed' in response
    if not success:
      sys.stderr.write('%s/n' % response)
    return success
  def at(self, planet):
    if not self.at_planet:
      return False
    if not planet:
      return False
    if type(self.coords) == types.ListType:
      return math.sqrt(math.pow(self.coords[0]-planet.location[0], 2) +
                       math.pow(self.coords[1]-planet.location[1], 2)) < 0.1
    return str(planet.planetid) in self.coords
  def scrap(self):
    if not self.at_planet:
      return False
    req = self.galaxy.opener.open(URL_SCRAP_FLEET % self.fleetid)
    response = req.read()
    fleet = None
    return 'Fleet Scrapped' in response
  def view(self):
    js = 'javascript:gm.centermap(%d, %d);' % (self.coords[0],
                                               self.coords[1])
    subprocess.call(['osascript', 'EvalJavascript.scpt', js ])


class Route:
  def __init__(self, galaxy, id, circular, name, points):
    self.galaxy = galaxy
    self.routeid = int(id)
    self.circular = circular
    self.name = name
    self.points = points
  def __getstate__(self): 
    return dict(filter(lambda x:  x[0] != 'galaxy',  self.__dict__.items()))
  def rename(self, name):
    formdata = {}
    formdata['name'] = name
    req = self.galaxy.opener.open(URL_RENAME_ROUTE % self.routeid,
                                  urllib.urlencode(formdata))
    response = req.read()
    if 'Route Renamed' in response: 
      self.name = name
    return self.name
    

class Galaxy:
  def __init__(self):
    self._planets = None
    self._fleets = None
    self._routes = None
    self._stars = None # alien planets
    self._logged_in = False
    self.jar = cookielib.LWPCookieJar()
    try:
      self.jar.load(CREDENTIAL_CACHE_FILE)
      self._logged_in = True
    except:
      pass
    self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.jar))
  def login(self, u='', p='', force=False):
    if force or not self._logged_in:
      self.opener.open(URL_LOGIN,
        urllib.urlencode(dict(usernamexor=u, passwordxor=p)))
      self.jar.save(CREDENTIAL_CACHE_FILE)
      self._logged_in = True
    else:
      sys.stderr.write("using stored credentials\n")

  def get_planet(self, id):
    for p in self.planets:
      if id == p.planetid:
        return p
    return None
    
  def find_route(self, query):
    if type(query) == types.StringType:
      for route in self.routes.values():
        if route.name == query:
          return route
      return None
    if type(query) == types.IntType:
      try:
        return self.routes[query]
      except KeyError:
        return None

  def find_fleet(self, query):
    if type(query) == types.IntType:
      for f in self.fleets:
        if query == f.fleetid:
          return f
      return None
    return None
    
  def find_planet(self, query):
    if type(query) == types.StringType:
      for p in self.planets:
        if query == p.name:
          return p
      return None
    if type(query) == types.IntType:
      for p in self.planets:
        if query == p.planetid:
          return p
      return None
    return None
    
  def load_all_planets(self):
    all_loaded = True
    for p in self.planets:
      all_loaded = p._loaded and all_loaded
    if not all_loaded:
      sys.stderr.write("loading all planets\n")
      for p in self.planets:
        p.load()
    return None
    
  def load_all_fleets(self):
    all_loaded = True
    for f in self.fleets:
      all_loaded = f._loaded and all_loaded
    if not all_loaded:
      sys.stderr.write("loading all fleets\n")
      for f in self.fleets:
        f.load()
      self.write_fleet_cache()
    return None
    
  def my_planets_near(self, pivot):
    survey = []
    for p in self.planets:
      if p != pivot:
        survey.append({'planet': p, 'distance': pivot.distance_to(p)})
    survey.sort(lambda a, b: cmp(a['distance'], b['distance']))
    return survey

  @property
  def routes(self):
    if self._routes: return self._routes
    self.load_routes()
    return self._routes
    
  @property
  def planets(self):
    if self._planets: return self._planets
    
    self.load_planet_cache()
    if self._planets: return self._planets
    
    sys.stderr.write('no planet cache\n')
    i=1
    planets = []
    while True:
      try:
        req = self.opener.open(URL_PLANETS % i)
        soup = BeautifulSoup(json.load(req)['tab'])
        for row in soup('tr')[1:]:
          cells=row('td')
          planetid=re.search(r'/planets/([0-9]*)/',
                             str(row('td')[0])).group(1)
          name = str(cells[4].string)
          coords = re.search(r'\(([0-9.]+),([0-9.]+)\)', str(row('td')[9]))
          location = map(lambda x: float(x), coords.groups())

# </th><th class="rowheader">Name</th>
# <th class="rowheader">Society</th>
# <th class="rowheader">Population</th>
# <th class="rowheader">Tax Rate</th>
# <th class="rowheader">Tariff Rate</th>
#<td>\n <img src=\"/site_media/center.png\" \n class=\"noborder\"\n onclick=\"gm.centermap(1636.382371,1472.795540);\"\n title=\"center on planet\"/>

          planets.append(Planet(self, planetid, name, location))
        i += 1
      except urllib2.HTTPError:
        sys.stderr.write('http error\n')
        break
      except KeyError:
        sys.stderr.write('key error\n')
        break
    self._planets = planets
    self.write_planet_cache()
    return planets

  @property
  def fleets(self):
    if self._fleets: return self._fleets

    self.load_fleet_cache()
    if self._fleets: return self._fleets

    i=1
    fleets = []
    while True:
      try:
        req = self.opener.open(URL_FLEETS % i)
        soup = BeautifulSoup(json.load(req)['tab'])
        for row in soup('tr')[1:]:
          cells=row('td')
          fleetid=re.search(r'/fleets/([0-9]*)/',
                             str(row('td')[0])).group(1)
#class=\"rowheader\"/>\n      <th class=\"rowheader\">ID</th><th
#class=\"rowheader\">Ships</th>\n      <th
#class=\"rowheader\">Disposition</th><th
#class=\"rowheader\">Destination</th>\n      <th
#class=\"rowheader\">Att.</th><th class=\"rowheader\">Def.</th>\n
          coords = parse_coords(
            re.search(r'gm.centermap(\([0-9.,]+\))', str(row)).group(1))
          at_planet = bool(re.search(r'\'scrapfleet\':[0-9]+', str(row)))
          fleets.append(Fleet(self, fleetid, coords, at=at_planet))
        i += 1
      except urllib2.HTTPError:
        break
      except KeyError:
        break
    self._fleets = fleets
    self.write_fleet_cache()
    return fleets
    
  def load_routes(self):
    formdata = {}
    formdata['0'] = 1
    formdata['getnamedroutes'] = 'yes'
    req = self.opener.open(URL_SECTORS,
                           urllib.urlencode(formdata))        
    response = req.read()
    j = json.loads(response)

    routes = self.parse_routes(j)
    if self._routes:
      self._routes.update(routes)
    else:
      self._routes = routes
    return self._routes

  def load_raw_sectors(self, bounding_box):
    formdata = {}
    routes = {}

    topx = int(bounding_box[0][0])/5
    topy = int(bounding_box[0][1])/5
    bottomx = int(bounding_box[1][0])/5
    bottomy = int(bounding_box[1][1])/5
    #print "%s,%s %s,%s" % (str(topx), str(topy), str(bottomx), str(bottomy))

    for x in range(topx, bottomx+1):
      for y in range(topy, bottomy+1):
        sector = x * 1000 + y
        formdata[str(sector)] = 1
    if routes:
      formdata['getnamedroutes'] = 'yes'
    req = self.opener.open(URL_SECTORS,
                           urllib.urlencode(formdata))        
    response = req.read()
    #sys.stderr.write('%s\n' % response)
    return response

  def load_sectors(self, bounding_box):
    j = json.loads(self.load_raw_sectors(bounding_box))

    unowned_planets = []
    owned_planets = []
    # parse the result, looking for planetary data
    secs = j["sectors"]["sectors"]
    for secnum in secs:
      #print "sector " + str(secnum)
      planets = secs[secnum]["planets"]
      for pnum in planets:
        #print "\tplanet " + str(pnum)
        try:
          p = planets[pnum]
          pid = int(p["i"])
          owner = int(p.get("o", 0))
          locationx = float(p["x"])
          locationy = float(p["y"])
          name = str(p["n"])
          planet = Planet(self, pid, name, [ locationx, locationy ])
          #print planet
          if owner == 0:
            unowned_planets.append(planet)
          else:
            owned_planets.append(planet)
        except:
          pass
    result = {}
    result["planets"] = {}
    result["planets"]["unowned"] = unowned_planets
    result["planets"]["owned"] = owned_planets
    result["routes"] = self.parse_routes(j)
    return result

  def parse_routes(self, j):
    routes = {}
    for key, value in j['sectors']['routes'].iteritems():
      if re.match(r'[\[,.\]0-9 ]+$', value['p']): # check input
        p = eval(value['p'])
        n = "Unnamed Route (%d)" % int(key)
        if 'n' in value.keys():
          n = str(value['n'])
        routes[int(key)] = Route(self, int(key), value['c'], n, p)
    return routes

  def load_sector_at(self, location):
    return self.load_sectors([location, location])

  def load_raw_sector_at(self, location):
    return self.load_raw_sectors([location, location])

  def create_route(self, name, circular, *points):
    formdata = {}
    formdata['name'] = name
    formdata['circular'] = str(circular).lower()
    formdata['route'] = ','.join(map(lambda p: 
                                     '/'.join(map(lambda x: str(x), p)), 
                                     points))
    req = self.opener.open(URL_BUILD_ROUTE,
                           urllib.urlencode(formdata))
    response = req.read()
    route = None
    if 'Route Built' in response: 
      j = json.loads(response)
      routeid = int(j['sectors']['routes'].keys()[0])
      route = Route(self, routeid, circular, name, points)
      self.routes[routeid] = route
    return route
      
  def write_planet_cache(self):
    # TODO: planets fail to pickle due to a lock object, write a reduce
    print "writing planet cache..."
    self.write_cache(PLANET_CACHE_FILE, self._planets)
    return None

  def load_planet_cache(self):
    self._planets = self.load_cache(PLANET_CACHE_FILE )
    return None

  def write_fleet_cache(self):
    print "writing fleet cache..."
    self.write_cache(FLEET_CACHE_FILE, self._fleets)
    return None

  def load_fleet_cache(self):
    self._fleets = self.load_cache(FLEET_CACHE_FILE )
    if self._fleets:
      for item in self._fleets:
        if hasattr(item, 'home') and item.home:
          item.home = self.find_planet(item.home.planetid)
    return None

  def write_cache(self, filename, data):
    # need to bump the recursion limit to let it work
    sys.setrecursionlimit(10000)
    try:
      cache_file = open(filename + ".tmp", 'w')
      pickle.dump(data, cache_file)
      cache_file.flush()
      cache_file.close()
      os.rename(filename + ".tmp", filename)
    except Exception as e:
      print "exception writing cache"
      print type(e)
      print e
      pass
    return None

  def load_cache(self, filename):
    sys.stderr.write("loading cached data from %s...\n" % filename)
    cache_data = None
    try: 
      if (time.time() - os.stat(filename).st_mtime) < CACHE_STALE_TIME:
        cache_file = open(filename, 'r')
        cache_data = pickle.load(cache_file)
        cache_file.close()
        for item in cache_data:
          item.galaxy = self
        sys.stderr.write("loaded cached data from %s\n" % filename)
      else:
        sys.stderr.write("cached data in %s is stale\n" % filename)
        pass
    except OSError:
        sys.stderr.write("cache file %s is missing or corrupt\n" % filename)
    return cache_data
