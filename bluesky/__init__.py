''' BlueSky: The open-source ATM simulator.'''
import importlib
# from bluesky import settings, stack
from bluesky.pathfinder import resource


__all__ = ['settings', 'stack', 'tools', 'cmdargs']

# Constants
BS_OK = 0
BS_ARGERR = 1
BS_FUNERR = 2
BS_CMDERR = 4

# simulation states
INIT, HOLD, OP, END = list(range(4))

# Startup flags
mode = ''
gui = ''

# Main singleton objects in BlueSky
ref = None
net = None
traf = None
navdb = None
sim = None
scr = None
server = None

def reload_submodules():
    """
    Reload all submodules dynamically except for excluded ones.
    If 'bluesky.stack' is present, reload it first.
    """
    import sys
    import importlib

    # A tuple is slightly faster for iteration than a set here
    excluded_modules = (
        'bluesky.resources',
        'bluesky.pathfinder',
        'bluesky.plugins',
        'bluesky.settings'
    )

    # 1. Filter dynamically using a list comprehension and any()
    modules_to_reload = [
        name for name, mod in list(sys.modules.items())
        if mod is not None
        and (name.startswith('bluesky.'))
        and not any(name == exc or name.startswith(f"{exc}.") for exc in excluded_modules)
    ]

    # 2. Sort to push 'bluesky.stack' to the front
    # In Python, False evaluates to 0 and True evaluates to 1.
    # So, (name != 'bluesky.stack') is 0 for the stack module, placing it first.
    # Needed so submodules can register correctly!!!
    modules_to_reload.sort(key=lambda name: name != 'bluesky.stack')

    #print(modules_to_reload)
    # 3. Execute the reloads
    for name in modules_to_reload:
        try:
            importlib.reload(sys.modules[name])
            #print(f"Successfully reloaded: {name}")
        except Exception as e:
            print(f"Failed to reload {name}: {e}")



def init(mode='sim', configfile=None, scenfile=None, discoverable=False,
         gui=None, detached=False, workdir=None, group_id=None, **kwargs):
    ''' Initialize bluesky modules.

        Arguments:
        - mode: Running mode of this bluesky process [sim/client/server]
        - configfile: Load a different configuration file [filename]
        - scenfile: Start with a running scenario [filename]
        - discoverable: Make server discoverable through UDP (only relevant
          when this process is running a server) [True/False]
        - gui: Gui type (only when mode is client or server) [qtgl/pygame/console]
        - detached: Run with or without networking (only when mode is sim) [True/False]
        - workdir: Pass a custom working directory (instead of cwd or ~/bluesky)
        - group_id: Explicitly set (part of) the connection identifier string.
                    Server does this when spawning a node
    '''

    # Argument checking
    assert mode in ('sim', 'client', 'server'), f'BlueSky init: Unrecognised mode {mode}. '\
        'Possible modes are sim, client, and server.'
    assert gui in (None, 'qtgl', 'pygame', 'console'), f'BlueSky init: Unrecognised gui type {gui}. '\
        'Possible types are qtgl, pygame, and console.'
    if discoverable:
        assert mode == 'server', 'BlueSky init: Discoverable can only be set in server mode.'
    if scenfile:
        assert mode != 'client', 'BlueSky init: Scenario file cannot be passed to a client.'
    if gui:
        assert mode != 'sim' or gui == 'pygame', 'BlueSky init: Gui type shouldn\'t be specified in sim mode.'
    if detached:
        assert mode == 'sim', 'BlueSky init: Detached operation is only available in sim mode.'

    # Keep track of mode and gui type.
    globals()['mode'] = mode
    globals()['gui'] = gui

    global server, traf, sim, scr, net, navdb

    # Initialise resource localisation, and set custom working directory if present
    from bluesky import pathfinder
    pathfinder.init(workdir)

    # Initialize global settings, possibly loading a custom config file
    from bluesky import settings
    settings.init(configfile)
    reload_submodules()
    
    from bluesky import stack, tools

    # Initialise tools
    from bluesky import tools
    tools.init()

    # Initialise reference data object
    from bluesky import refdata
    globals()['ref'] = refdata.RefData()

    # Load navdatabase in all versions of BlueSky
    # Only the headless server doesn't need this
    if mode == "sim" or gui is not None:
        from bluesky.navdatabase import Navdatabase
        navdb = Navdatabase()

    # If mode is server-gui or server-headless start the networking server
    if mode == 'server':
        from bluesky.network.server import Server
        server = Server(discoverable, configfile, scenfile, workdir)

    # The remaining objects are only instantiated in the sim nodes
    if mode == 'sim':
        from bluesky.traffic import Traffic
        from bluesky.simulation import Simulation
        if gui == 'pygame':
            from bluesky.ui.pygame.screen import Screen
            from bluesky.network.detached import Node
        else:
            from bluesky.simulation import ScreenIO as Screen
            if detached:
                from bluesky.network.detached import Node
            else:
                from bluesky.network.node import Node

        from bluesky.core import varexplorer

        # Initialise singletons
        traf = Traffic()
        sim = Simulation()
        scr = Screen()
        net = Node(group_id)

        # Initialize remaining modules
        varexplorer.init()
    elif mode == 'client' or (mode == 'server' and gui is not None):
        # For clients we initialise the traffic object as a network
        # proxy. When BlueSky is run as a full application, server
        # and client share one process.
        from bluesky.core.trafficproxy import TrafficProxy

        # Initialise singletons
        traf = TrafficProxy()

    from bluesky.core import plugin
    plugin.init(mode)
    from bluesky import stack
    stack.init(mode)
    if scenfile and mode == 'sim':
        stack.stack(f'IC {scenfile}')


def __getattr__(name):
    if name in __all__:
        return importlib.import_module(f'.{name}', __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
