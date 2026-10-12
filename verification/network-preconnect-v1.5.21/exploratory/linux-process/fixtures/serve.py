#!/usr/bin/env python3
"""Bounded local wire fixtures usable by Go clients, live cores or adb reverse.

Print one ready JSON, then accept JSON lines {"action":"snapshot"} or
{"action":"stop"}. All servers and all forwarding destinations are loopback.
Fixture credentials and the public test certificate are not user secrets.
"""
import argparse
import json
import sys
from benchmark import OUT, Socks, Target, Wire, certificates


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry-setup-ms',type=int,default=80)
    parser.add_argument('--entry-phase-ms',type=int,default=15)
    parser.add_argument('--exit-phase-ms',type=int,default=35)
    args=parser.parse_args()
    assert all(0<=value<=500 for value in vars(args).values())
    wire=Wire();server_tls,_=certificates();target=Target(wire,server_tls)
    exit_node=Socks('exit',wire,('bench.invalid',target.port),0,args.exit_phase_ms)
    entries=[Socks(name,wire,('127.0.0.1',exit_node.port),args.entry_setup_ms,args.entry_phase_ms) for name in ('entryA','entryB')]
    def node(value):
        return {'name':value.name,'host':'127.0.0.1','port':value.port,'username':value.user.decode(),'password':value.password.decode()}
    try:
        print(json.dumps({'schema':1,'ready':True,'entries':[node(value) for value in entries],'fixedExit':node(exit_node),
                          'target':{'url':'https://bench.invalid:'+str(target.port)+'/probe','status':204,'host':'bench.invalid','port':target.port,'alpn':'http/1.1'},
                          'trustedFixtureCertificate':(OUT/'fixture-cert.pem').read_text(),'allDestinationsLoopback':True,
                          'serverDelayMs':vars(args),'scope':'Synthetic wire fixtures; no user accounts, production pool, WAN or Android acceptance claim'}),flush=True)
        for line in sys.stdin:
            request=json.loads(line)
            if request.get('action')=='stop':
                print(json.dumps({'stopped':True}),flush=True);break
            assert request.get('action')=='snapshot'
            with wire.lock:
                rows=list(wire.rows)
            print(json.dumps({'schema':1,'wireEvents':rows,'actualTcpWireExecution':True}),flush=True)
    finally:
        for entry in entries:entry.close()
        exit_node.close();target.close()


if __name__=='__main__':main()
