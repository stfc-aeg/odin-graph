"""
Graphing Adapter for Odin Control.
Implements means of monitoring a stream of data, with specified time intervals.
this is done so that GUI elements (such as using chart.js) can be easily implemented

Ashley Neaves, STFC Detector Systems Software Group"""

import logging

from odin.adapters.adapter import (ApiAdapter, ApiAdapterRequest,
                                   ApiAdapterResponse, request_types, response_types)
from odin.util import decode_request_body
from odin.adapters.parameter_tree import ParameterTree, ParameterTreeError
from tornado.ioloop import PeriodicCallback, IOLoop
import time
import json

from .dataset import GraphDataset, AvgGraphDataset


class GraphAdapter(ApiAdapter):

    def __init__(self, **kwargs):
        super(GraphAdapter, self).__init__(**kwargs)
        """Initialize GraphAdapter object."""

        self.dataset_config = self.options.get("config_file")

        self.dataset_trees = {}
        self.datasets = {}

        self.load_config()
        self.initialize_tree() 

    def load_config(self):
        """Load json config file and add datasets accordingly."""

        logging.debug("loading config file")

        with open(self.dataset_config) as f:
            config = json.load(f)
            
            for key, value in self.get_last_dict(config):
                try:
                    if value.get('average', False):
                        self.add_avg_dataset(value['interval'], value['retention'], value['source'], value['location'])
                    else:
                        self.add_dataset(value['adapter'], value['get_path'], value['interval'], value['retention'], value['location'])
                except KeyError as err:
                    logging.error("Error creating dataset %s: %s", (value['location']), err)

    def initialize_tree(self):
        """Generate ParameterTree object. """
        self.param_tree = ParameterTree(self.dataset_trees)

    def add_to_dict(self, location, data, dict):
        """Add a value to a nested dictionary given its location."""
        param_dict = dict
        parts = location.strip("/").split("/")
        for path_part in parts:
            try:
                if path_part != parts[-1]:
                    param_dict = param_dict[path_part]
                else:
                    param_dict[path_part] = data
            except KeyError:
                param_dict[path_part] = {}
                param_dict = param_dict[path_part]

    def iterate_dict_values(self, dictionary, endpoints=[]):
        """Return all end values in a nested dictionary."""
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.iterate_dict_values(value)
            else:
                endpoints.append(value)
        return endpoints
    
    def get_last_dict(self, dictionary, endpoints=[]):
        """Extract innermost dictionary including its key from a nested dictionary."""
        for outer_key, outer_value in dictionary.items():
            for inner_key, inner_value in outer_value.items():
                if isinstance(inner_value, dict):
                    self.get_last_dict(outer_value)
                else:
                    if (outer_key, outer_value) not in endpoints:
                        endpoints.append((outer_key, outer_value))
        return endpoints

    def add_dataset(self, adapter, path, interval, retention, location):
        """Create GraphDataset object and add to dataset dictionaries."""

        dataset = GraphDataset(
            time_interval=interval,
            adapter=adapter,
            get_path=path,
            retention=retention,
            location=location
            )

        self.add_to_dict(location, dataset.param_tree, self.dataset_trees)
        self.add_to_dict(location, dataset, self.datasets)

    def add_avg_dataset(self, interval, retention, source, location):
        """Create AvgGraphDataset object and add to dataset dictionaries."""

        source_location = source.strip("/").split("/")
        dataset_location = self.datasets
        for path_part in source_location:
            dataset_location = dataset_location[path_part]
        source_dataset = dataset_location
        # getting source dataset - variable location path length

        dataset = AvgGraphDataset(
            time_interval=interval,
            retention=retention,
            source=source_dataset,
            location=location 
        )

        self.add_to_dict(location, dataset.param_tree, self.dataset_trees)
        self.add_to_dict(location, dataset, self.datasets)

    def initialize(self, adapters):
        """Start data loops for each dataset. """

        self.adapters = dict((k, v) for k, v in adapters.items() if v is not self)

        logging.debug("Received following dict of Adapters: %s", self.adapters)

        for dataset in self.iterate_dict_values(self.datasets):
            dataset.get_adapter(self.adapters)
            dataset.data_loop.start()

    def get(self, path, request):
        """
        Handle an HTTP GET request.

        This method handles an HTTP GET request, returning a JSON response.

        :param path: URI path of request
        :param request: HTTP request object
        :return: an ApiAdapterResponse object containing the appropriate response
        """

        try:
            response = self.param_tree.get(path)
            content_type = 'application/json'
            status = 200
        except ParameterTreeError as param_error:
            response = {'response': "Graphing Adapter GET Error: %s".format(param_error)}
            content_type = 'application/json'
            status = 400

        return ApiAdapterResponse(response, content_type=content_type, status_code=status)
