# Author: Kelvin Lai <kelvin@firststreet.org>
# Copyright: This module is owned by First Street Foundation

# Standard Imports
import logging

# Internal Imports
from firststreet.api import csv_format
from firststreet.api.api import Api
from firststreet.errors import InvalidArgument
from firststreet.models.fema import FemaNfip


class Fema(Api):
    """This class receives a list of search_items and handles the creation of a fema product from the request.

        Methods:
            get_nfip: Retrieves a list of Fema Nfip for the given list of IDs
        """

    def get_nfip(self, search_item, location_type, csv=False, connection_limit=100, output_dir=None, extra_param=None):
        """Retrieves fema nfip product data from the First Street Foundation API given a list of search_items and
        returns a list of Fema Nfip objects.

        Args:
            search_item (list/file): A First Street Foundation IDs, lat/lng pair, address, or a
                file of First Street Foundation IDs
            location_type (str): The location lookup type
            csv (bool): To output extracted data to a csv or not
            connection_limit (int): max number of connections to make
            output_dir (str): The output directory to save the generated csvs
            extra_param (str): Extra parameter to be added to the url

        Returns:
            A list of Fema Nfip
        Raises:
            InvalidArgument: The location provided is empty
            TypeError: The location provided is not a string
        """

        if not location_type:
            raise InvalidArgument(location_type)
        elif not isinstance(location_type, str):
            raise TypeError("location is not a string")

        # Get data from api and create objects
        api_datas = self.call_api(search_item, "fema", "nfip", location_type,
                                  connection_limit=connection_limit, extra_param=extra_param)
        product = [FemaNfip(api_data) for api_data in api_datas]

        if csv:
            csv_format.to_csv(product, "fema", "nfip", location_type, output_dir=output_dir)

        logging.info("Fema Nfip Data Ready.")

        return product
