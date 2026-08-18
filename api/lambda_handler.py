import os
import sys
from .routes import RouteHandler

route_handler = RouteHandler()

def handler(event, context=None):
    return route_handler.route_request(event)