# -*- coding: utf-8 -*-
"""Pyramid helper. Includes a path helper that allows you to pass a route name
for inspection. Inspects URL rules and view docstrings.

Inspecting a route and its view::

    from pyramid_apispec.helpers import add_pyramid_paths

    @view_config(route_name='foo_route', renderer='json')
    def foo_view():
        \"""A greeting endpoint.

        ---
        x-extension: value
        get:
            description: get a greeting
            responses:
                200:
                    description: a pet to be returned
                    schema:
                        $ref: #/definitions/SomeFooBody
        \"""
        return 'hi'

    @view_config(route_name='openapi_spec', renderer='json')
    def api_spec(request):
        spec = APISpec(
            title='Some API',
            version='1.0.0',
            plugins=[
                'apispec.ext.marshmallow'
            ],
        )
        # using marshmallow plugin here
        spec.definition('SomeFooBody', schema=MarshmallowSomeFooBodySchema)

        # inspect the `foo_route` and generate operations from docstring
        add_pyramid_paths(spec, 'foo_route', request=request)

        # inspection supports filtering via pyramid add_view predicate arguments
        add_pyramid_paths(
            spec, 'bar_route', request=request, request_method='post')
        return spec.to_dict()


"""
from __future__ import absolute_import

from apispec.utils import load_operations_from_docstring, load_yaml_from_docstring

from pyramid.threadlocal import get_current_request

# py 2/3 compat
try:
    import basestring

    string_type = basestring
except ImportError:
    string_type = str


def is_string(val):
    return isinstance(val, string_type)


ALL_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def add_pyramid_paths(
    spec,
    route_name,
    request=None,
    request_method=None,
    operations=None,
    autodoc=True,
    **kwargs
):
    """

    Adds a route and view info to spec

    :param spec:
        ApiSpec object
    :param route_name:
        Route name to inspect
    :param request:
        Request object, if `None` then `get_current_request()` will be used
    :param request_method:
        Request method predicate
    :param operations:
        Operations dict that will be used instead of introspection
    :param autodoc:
        Include information about endpoints without markdown docstring
    :param kwargs:
        Additional kwargs for predicate matching
    :return:

    """
    if request is None:
        request = get_current_request()

    registry = request.registry
    introspector = registry.introspector
    route = introspector.get("routes", route_name)
    introspectables = introspector.related(route)

    # needs to be rewritten to internal name
    if request_method:
        kwargs["request_methods"] = request_method

    for maybe_view in introspectables:
        if not is_view(maybe_view) or not check_methods_matching(maybe_view, **kwargs):
            continue

        pattern = route["pattern"]
        if not pattern.startswith("/"):
            pattern = "/%s" % pattern

        spec.add_path(
            pattern, operations=get_operations(maybe_view, operations, autodoc=autodoc)
        )


def is_view(introspectable):
    return introspectable.category_name == "views"


def check_methods_matching(view, **kwargs):
    for kw in kwargs.keys():
        # request_methods can be either a list of strings or a string
        # so lets normalize via sets
        if kw == "request_methods":
            if is_string(kwargs[kw]):
                kwargs[kw] = [kwargs[kw]]
            methods = view.get(kw) or ALL_METHODS
            if is_string(methods):
                methods = [methods]
            if not set(kwargs[kw] or []).intersection(methods):
                return False
        else:
            if not view.get(kw) == kwargs[kw]:
                return False
    return True


def get_operations(view, operations, autodoc=True):
    if operations is not None:
        return operations

    operations = {}

    # views can be class based
    if view.get("attr"):
        global_meta = load_operations_from_docstring(view["callable"].__doc__)
        if global_meta:
            operations.update(global_meta)
        f_view = getattr(view["callable"], view["attr"])
    # or just function callables
    else:
        f_view = view.get("callable")

    methods = view.get("request_methods")
    view_operations = load_operations_from_docstring(f_view.__doc__)
    if not view_operations:
        view_operations = {}
        if is_string(methods):
            methods = [methods]
        if not methods:
            methods = ALL_METHODS[:]
        operation = load_yaml_from_docstring(f_view.__doc__)
        if operation:
            for method in methods:
                view_operations[method.lower()] = operation
        elif autodoc:
            for method in methods:
                view_operations.setdefault(method.lower(), {"responses": {}})
    operations.update(view_operations)

    return operations
