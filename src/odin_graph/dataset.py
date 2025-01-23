import logging

from odin.adapters.adapter import (ApiAdapter, ApiAdapterRequest,
                                   ApiAdapterResponse, request_types, response_types)
from odin.util import decode_request_body
from odin.adapters.parameter_tree import ParameterTree, ParameterTreeError
from tornado.ioloop import PeriodicCallback, IOLoop
import time
import json

class GraphDataset():

    def __init__(self, time_interval, adapter, get_path, retention, location):
        """Initialize GraphDataset object.
        
        Keyword arguements:
        time_interval -- interval at which to sample
        adapter -- adapter containing data to sample
        get_path -- parameter tree path within adapter
        retention -- amount of history to store
        location -- graph parameter tree location to store data
        """

        self.time_interval = time_interval
        self.data = []
        self.timestamps = []
        self.adapter_name = adapter
        self.adapter = None
        self.get_path = get_path
        self.retention = retention
        self.location = location

        self.max = max(self.data, default=0)
        self.min = min(self.data, default=0)

        self.data_loop = PeriodicCallback(self.get_data, self.time_interval * 1000)

        logging.debug("Created Dataset %s, interval of %f seconds", location, self.time_interval)

        self.param_tree = ParameterTree({
            "data": (lambda: self.data, None),
            "timestamps": (lambda: self.timestamps, None),
            "interval": (self.time_interval, None),
            "retention": (self.retention * self.time_interval, None),
            "loop_running": (lambda: self.data_loop.is_running(), None),
            "max": (lambda: self.max, None),
            "min": (lambda: self.min, None)
        })

    def get_data(self):
        """Add newest sample to data.
        
        Removes any data older than retention.
        Updates min/max values with currently retained data.
        """
        cur_time = time.strftime("%H:%M:%S", time.localtime())
        response = self.adapter.get(self.get_path, ApiAdapterRequest(None))
        data = response.data[self.get_path.split("/")[-1]]

        self.data.append(data)
        self.timestamps.append(cur_time)
        if len(self.data) > self.retention:
            self.data.pop(0)
            self.timestamps.pop(0)

        self.max = max(self.data)
        self.min = min(self.data)

    def get_adapter(self, adapter_list):
        """Gets adapter from adapter list."""
        self.adapter = adapter_list[self.adapter_name]

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class AvgGraphDataset(GraphDataset):
    
    def __init__(self, time_interval, retention, source, location):
        super().__init__(time_interval, adapter=None, get_path=None, retention=retention, location=location)
        """Initialize AvgGraphDataset object.
        
        Keyword arguements:
        source -- location of GraphDataset object to reference
        """
        
        self.source = source
        self.num_points_get = int(self.time_interval / self.source.time_interval)

        self.min_list = []
        self.max_list = []

        logging.debug("Created averaging dataset " + location + ", averaging from %s", self.source)

    def get_data(self):
        """Finds average of newest data slice and adds to data.
        
        Removes any data older than retention.
        """
        cur_time = time.strftime("%H:%M:%S", time.localtime())
        data = self.source.data[-self.num_points_get:]  # slice, get last x elements

        data_min = min(data)
        data_max = max(data)
        # finds min/max of actual data slice

        data = data = sum(data) / len(data)
        # averages data slice

        self.min_list.append(data_min)
        self.max_list.append(data_max)
        # adds slice min/max to lists

        self.data.append(data)
        self.timestamps.append(cur_time)

        if len(self.data) > self.retention:
            self.data.pop(0)
            self.timestamps.pop(0)
            self.min_list.pop(0)
            self.max_list.pop(0)

        self.min = min(self.min_list)
        self.max = max(self.max_list)
        #finds min/max of min/max values retained from each slice

    def get_adapter(self, adapter_list):
        pass  # method empty on purpose as we don't need the adapter for this type of dataset
