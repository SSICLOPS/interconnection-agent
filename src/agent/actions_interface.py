import sys
import logging




async def action_no_op(*args, **kwargs):
    pass

async def action_die(*args, **kwargs):
    logging.info("Dying")
    sys.exit()
    
actions_mapping = {
    "No-op": action_no_op,
    "Die": action_die,
}