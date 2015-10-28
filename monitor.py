import sys
import json
from grapheneapi import GrapheneWebsocket, GrapheneWebsocketProtocol
from graphenebase import Memo, PrivateKey, PublicKey
import config
import re

try :
    import requests
except ImportError:
    raise ImportError( "Missing dependency: python-requests" )

""" PubKey Prefix
    Productive network: BTS
    Testnetwork: GPH """
prefix = "GPH"
#prefix = "BTS"

""" Callback on event
    This function will be triggered on a notification of the witness.
    If you subsribe (see below) to 2.6.*, the witness node will notify you of
    any chances regarding your account_balance """
class GrapheneMonitor(GrapheneWebsocketProtocol) :
    last_op      = "1.11.0"
    account_id   = "1"
    def __init__(self) :
        super().__init__()

    def printJson(self,d) : print(json.dumps(d,indent=4))

    def onAccountUpdate(self, data) :
        # Get Operation ID that modifies our balance
        opID         = api.getObject(data["most_recent_op"])["operation_id"]
        self.wsexec([self.api_ids["history"], "get_account_history", [self.account_id, self.last_op, 100, "1.11.0"]], self.process_operations)
        self.last_op = opID

    def process_operations(self, operations) :
        for operation in operations[::-1] :
            opID         = operation["id"]
            block        = operation["block_num"]
            op           = operation["op"][1]

            if not "amount" in op:
                continue

            # Get assets involved in Fee and Transfer
            fee_asset    = api.getObject(op["fee"]["asset_id"])
            amount_asset = api.getObject(op["amount"]["asset_id"])

            # Amounts for fee and transfer
            fee_amount   =    float(op["fee"]["amount"]) / float(10**int(fee_asset["precision"]))
            amount_amount= float(op["amount"]["amount"]) / float(10**int(amount_asset["precision"]))

            # Get accounts involved
            from_account = api.getObject(op["from"])
            to_account   = api.getObject(op["to"])

            # Decode the memo
            memo         = op["memo"]
            try : # if possible
                privkey = PrivateKey(config.memo_wif_key)
                pubkey  = PublicKey(memo["from"], prefix=prefix)
                memomsg = Memo.decode_memo(privkey, pubkey, memo["nonce"], memo["message"])
            except Exception as e: # if not possible
                print("--cannot decode-- %s" % e)
                continue

            # Print out
            print("last_op: %s | block:%s | from %s -> to: %s | fee: %f %s | amount: %f %s | memo: %s" % (
                      opID, block, 
                      from_account["name"], to_account["name"],
                      fee_amount, fee_asset["symbol"],
                      amount_amount, amount_asset["symbol"],
                      memomsg))

            # Parse the memo
            pattern       = re.compile('[A-Z0-9]{3}-[A-Z0-9-]{8}')
            searchResults = pattern.search(memomsg)
            if not searchResults:
                continue
            ref_code      = searchResults.group(0)

            email = ""    
            pattern       = re.compile('[a-z0-9][-a-z0-9_\+\.]*[a-z0-9]\@.+\.[a-z]+')
            searchResults = pattern.search(memomsg.lower())
            if searchResults:
                email      = searchResults.group(0)

            # Request to Faucet
            headers  = {'content-type': 'text/plain'}
            query = "refcode[code]=%s&refcode[account]=%s&refcode[asset_symbol]=%s&refcode[asset_amount]=%s&refcode[send_to]=%s" % (ref_code, from_account["name"], amount_asset["symbol"], op["amount"]["amount"], email)
            print("--- query: %s" % query)
            response = requests.post(config.faucet_url,
                                     params=query,
                                     headers=headers)

if __name__ == '__main__':
    ## Monitor definitions
    protocol = GrapheneMonitor
    protocol.last_op = config.last_op ## last operation logged
    protocol.account_id = "1.2.%s" % config.accountID.split(".")[2]  ## account to monitor

    ## Open Up Graphene Websocket API
    api      = GrapheneWebsocket(config.host, config.port, config.user, config.password, protocol)

    print(api)

    ## Set Callback for object changes
    api.setObjectCallbacks({config.accountID : protocol.onAccountUpdate})

    ## Run the Websocket connection continuously
    api.connect()
    api.run_forever()
