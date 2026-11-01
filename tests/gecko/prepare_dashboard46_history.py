"""Prepare the exact formal45 oracle inputs once they leave the original shallow checkout.

Keep the original three-group preparer and every original oracle unchanged.
Only this finite source-owned fourth group is added; no branch/depth changes.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

_path=Path(__file__).with_name('prepare_bridge42_history12.py')
_spec=importlib.util.spec_from_file_location('dashboard_original_history12',_path)
history=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(history)

DASHBOARD_GROUP = ('e15147246ceff2e1ed2ffd9a18df1fd17b03ddee',
 'cbb37b32ad11ec52bc91216185a033bf1d475e08',
 {'app/src/main/java/local/pocketchat/BrowserReading.java': ('9b9f5b2a117524adc423ba0c789dc40007d25425',
                                                             13188,
                                                             '5ad7bfa079acceb82062cd522d893de17ab29a6baf9742f6598e38fd837e76a0'),
  'app/src/main/java/local/pocketchat/BrowserReadingPolicy.java': ('73bcb001b0480845d43517a7a1eb2c11a3cdbd57',
                                                                   4631,
                                                                   '6388293450db6800e741e80c22fca74f528cefecbb68e641ec5ac6bc6b9466c0'),
  'app/src/main/java/local/pocketchat/ChatSession.java': ('c2111e2d6193506a2415c7015966d4f675e0f530',
                                                          69541,
                                                          '0e0d3b49066ac09c87f072b755d6702d2ded23c8ed66afe545dc7c34ffe4c61c'),
  'app/src/main/java/local/pocketchat/GeckoWebView.java': ('02452dcb4ac47f9a7765bbf014060fb7ec42162a',
                                                           70564,
                                                           '32e06089272bbbaf63ed94449ea208cd2feb930cc05a903ab3e83efb0f140546'),
  'tests/browser-reading-host/local/pocketchat/BrowserReadingHostTest.java': ('b0bfeb7fe4afd21c4a0675a5fbd4f1b199bf0493',
                                                                              25274,
                                                                              '8e29601536facc3c49a64346b523fdcc671159cfd2f8d414ec72a129a7bd9a3e'),
  'tests/browser-reading-host/local/pocketchat/ChatSession.java': ('7b9d6e6a28a7e8d38ca00a5bbdec990de61940dd',
                                                                   3063,
                                                                   '366b6de6e82de8ff8f71226bfb0f15a0125fcb66930f97e82e8c993a222c67ff'),
  'tests/gecko/GeckoIntegrationTestActivity.java': ('0a0bdfcf4acda4de28f50c869c8604237dd67598',
                                                    123686,
                                                    'd79a5f95b521a909a5ef5bfb0ce68a9156cea5f3bdea5657bdd571a705dc4f8f'),
  'tests/gecko/run_device.py': ('fb8e09d74ceddd57e1683e22b6f60f43f8d6e87f',
                                88701,
                                '54fa412be9f89e46d61597caf61b0246e451e6c9b5eebca592e36b05686ab8a6'),
  'tests/native43_source_compatibility.py': ('88ba6b6508f7570c178343c1b44690154ae47835',
                                             2100,
                                             'bcfd5225bcfd4062dce70fe831da0b376e0e624d561498831ce55a565582e535'),
  'tests/profile_native43_source_compatibility_test.py': ('5de03764a2f9cabe63b2b99b859f40454c720657',
                                                          8465,
                                                          '5c6dc562e63ae47ee6cd7978c968f373c5b3d4d5f988ff7642585142e884e6b8'),
  'tests/profile_reading45_source_compatibility_test.py': ('91d6f58c317a44f58fda00d060b71b57d0b87ed3',
                                                           5543,
                                                           '76724b7a447ee445897660f20cbaa871d6ed5512c991a2ceb4b4f00b251e21f4'),
  'tests/profile_reading_fit_completion_test.py': ('795280c2f436b7fbee75fda339bfb4d7ca2b8f10',
                                                   18994,
                                                   'c6292966924bca62e0ac38402d4c65a520a262cee3de6fbe0e5c5076f5c8dda0'),
  'tests/profile_reading_zoom_trace_test.py': ('48d994d2a9819891f686089958b62112a65ca5cf',
                                               13305,
                                               '0380c60b94a0512ea95dbb652360dd0090047db7a823342fa8936842a1105009'),
  'tests/reading45_source_compatibility.py': ('3bcf8fb34f306dc532c27632ae84cf22a8f5322f',
                                              1859,
                                              'aa2d5fa6f36f21a3a2b89786673c683efcded1de989b1dd362a8dec9e17576cf')})


def prepare_dashboard_history(root, environment=None):
    root=Path(root).resolve()
    value=history.prepare_original_history(root,environment)
    fetched=list(value['fetchedOwnerCommits'])
    try:
        ready=history.verify_group(root,DASHBOARD_GROUP)
    except history.MissingHistoricalInput:
        state=history.authorize_fetch(root,os.environ if environment is None else environment)
        try:
            history.checked(root,'fetch','--no-tags','--depth=1','--no-write-fetch-head','origin',DASHBOARD_GROUP[0])
        finally:
            history.require(history.checkout_state(root)==state,'exact historical input fetch changed checkout')
        fetched.append(DASHBOARD_GROUP[0])
        ready=history.verify_group(root,DASHBOARD_GROUP)
    return dict(value,groups=[*value['groups'],ready],fetchedOwnerCommits=fetched,
                scope='Finite original source-oracle input preparation only; original tests still run unchanged.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args()
    print(json.dumps(prepare_dashboard_history(args.root),sort_keys=True))
