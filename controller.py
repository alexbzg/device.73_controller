#!/usr/bin/python
#coding=utf-8

from twisted.internet import reactor
from twisted.spread import pb
from twisted.internet.protocol import Protocol, ReconnectingClientFactory

from time import sleep
from pyA20.gpio import gpio, port

import os, sys, json

confFile = 'conf'
if len( sys.argv ) > 1:
    confFile = sys.argv[1]
appPath = os.path.dirname( os.path.realpath( '__file__' ) )
conf = json.load( open( appPath + '/' + confFile + '.json', 'r' ) )
devices = {}
pbConn = None

def getPin( no ):
    if no == 29:
        return port.PA7
    elif no == 31:
        return port.PA8
    elif no == 33:
        return port.PA9
    elif no == 35:
        return port.PA10
    elif no == 37:
        return port.PA20
    elif no == 12:
        return port.PD14
    elif no == 16:
        return port.PC4
    elif no == 18:
        return port.PC7
    elif no == 7:
        return port.PA6
    elif no == 32:
        return port.PG8
    elif no == 36:
        return port.PG9
    elif no == 38:
        return port.PG6
    elif no == 40:
        return port.PG7

class Device:
    def __init__( self, id, params ):
        self.id = id
        self.name = params['name']
        self.pin = getPin( params['pin'] )
        self.type = params['type']
        devices['id'] = self
        if self.type == 'switch' or self.type == 'pulse':
            gpio.setcfg( self.pin, gpio.OUTPUT )
            if self.type == 'pulse':
                self.interval = params['interval']
                gpio.output( self.pin, 0)
            elif self.type == 'switch':
                self.state = gpio.input( self.pin ) == 1

    def cmd( self, params ):
        if self.type == 'switch':
            if params['cmd'] == 'toggle':
                self.setState( not self.state )
            elif params['cmd'] == 'set':
                self.setState( params['state'] )
        elif self.type == 'pulse':
            if params['cmd'] == 'pulse':
                gpio.output( self.pin, 1 )
                reactor.callLater( self.interval, gpio.output, self.pin, 0 )


    def setState( self, state ):
        if self.type == 'switch' and self.state != state:
            gpio.output( self.pin, 1 if state else 0 )
            self.state = not self.state
            updateSrv( { 'devices': { 'id': { 'state': self.state } } } )

    def toDict( self ):
        r = { "name": self.name, "type": self.type }
        if self.type == "switch":
            r['state'] = self.state
        elif self.type == "pulse":
            r['interval'] = self.interval
        return r


gpio.init()
for k, v in conf['devices'].iteritems():
    Device( k, v )

       
def updateSrv( data ):
    if pbConnection:
        pbConnection.updateSrv( data )



class PBConnection( pb.Referenceable ):
    def remote_cmd( self, cmd ):
        if devices.has_key( cmd['device'] ):
            devices[ cmd['device'] ].cmd( cmd )

    def updateSrv( self, data ):
        if self.serverConnection:
            self.serverConnection.remote_data( data )

    def setServerConnection( self, serverConnection ):
        self.serverConnection = serverConnection

class RecPBClientFactory( pb.PBClientFactory, ReconnectingClientFactory ):
    maxDelay = 15

    def __init__( self ):
        pb.PBClientFactory.__init__( self )
        self.ipaddress = None

    def clientConnectionMade( self, broker ):
        global pbConnection
        print 'Connect to pb server'
        pb.PBClientFactory.clientConnectionMade( self, broker )
        d = self.getRootObject()
        pbConnection = PBConnection()
        d.addCallback( \
            lambda object: \
                pbConnection.setServerConnection ( \
                    object.callRemote( "connect", pbConnection, 
                        { 'id' : conf['id'], \
                        'devices': { id: dev.toDict() for id, dev in \
                            devices.iteritems() } } ) ) )

    def buildProtocol( self, addr ):
        return pb.PBClientFactory.buildProtocol( self, addr )

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason: ' + str( reason )
        if pbConnection:
            pbConnection = None
        ReconnectingClientFactory.clientConnectionLost(self, connector, \
                reason)

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason: ' + str( reason )
        ReconnectingClientFactory.clientConnectionLost(self, connector, \
                reason)
    


factory = RecPBClientFactory()

def connectServer():

    try:
        reactor.connectTCP( conf['pb']['host'], conf['pb']['port'], \
                factory )
    except Exception:
        print 'connection failed'
        connectServer()



connectServer()
reactor.run()


