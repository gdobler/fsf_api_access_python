# Author: Kelvin Lai <kelvin@firststreet.org>
# Copyright: This module is owned by First Street Foundation

# Standard Imports
import asyncio

# External Imports
import logging
import tqdm
import aiohttp
import ssl
import certifi

# Internal Imports
import firststreet.errors as e

DEFAULT_SUMMARY_VERSION = 'v1'


class Http:
    """This class handles the communication with the First Street Foundation API by constructing and sending the HTTP
        requests, and handles any errors during the execution.
        Attributes:
            api_key (str): A string specifying the API key.
            version (str): The version to call the API with
        Methods:
            execute: Sends a request to the First Street Foundation API for the specified endpoint
        """

    def __init__(self, api_key, version=None):
        if version is None:
            version = DEFAULT_SUMMARY_VERSION

        self.api_key = api_key
        self.options = {'url': "https://api.firststreet.org",
                        'headers': {
                            'Content-Encoding': 'gzip',
                            'Content-Type': 'text/html',
                            'User-Agent': 'python/firststreet',
                            'Accept': 'application/vnd.api+json',
                            'Authorization': 'Bearer %s' % api_key
                        }}
        self.version = version

    async def endpoint_execute(self, endpoints, limit=100):
        """Asynchronously calls each endpoint and returns the JSON responses
        Args:
            endpoints (list): List of endpoints to get
            limit (int): max number of connections to make
        Returns:
            The list of JSON responses corresponding to each endpoint
        """
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

        connector = aiohttp.TCPConnector(limit_per_host=limit, ssl=ssl_ctx)
        session = aiohttp.ClientSession(connector=connector)

        try:
            tasks = [asyncio.create_task(self.execute(endpoint, session)) for endpoint in endpoints]
            for t in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
                await t
            ret = [t.result() for t in tasks]

        finally:
            await session.close()

        return ret

    async def execute(self, endpoint, session):
        """Executes the endpoint for the given endpoint with the open session
        Args:
            endpoint (str): The endpoint to get from
            session (ClientSession): The open session
        Returns:
            The JSON reponse or an empty body if error
        Raises:
            _network_error: if an error occurs
        """
        headers = self.options.get('headers')

        retry = 0
        while retry < 5:

            try:
                async with session.get(endpoint[0], headers=headers) as response:

                    rate_limit = self._parse_rate_limit(response.headers)

                    if endpoint[2] == 'tile':
                        body = await response.read()

                        if response.status != 200 and response.status != 500:
                            raise self._network_error(self.options, rate_limit,
                                                      status=response.reason, message=response.status)
                        elif response.status == 500:
                            logging.info(
                                "Error retrieving tile from server. Check if the coordinates provided are correct: {}"
                                .format(endpoint[1]))
                            return {"coordinate": endpoint[1], "image": None, 'valid_id': False}

                        return {"coordinate": endpoint[1], "image": body}

                    else:
                        body = await response.json(content_type=None)

                        if response.status != 200 and response.status != 404 and response.status != 500:
                            raise self._network_error(self.options, rate_limit, error=body.get('error'))

                        error = body.get("error")
                        if error:
                            search_item = endpoint[1]
                            product = endpoint[2]
                            product_subtype = endpoint[3]

                            if product == 'adaptation' and product_subtype == 'detail':
                                return {'adaptationId': search_item, 'valid_id': False}

                            elif product == 'historic' and product_subtype == 'event':
                                return {'eventId': search_item, 'valid_id': False}

                            else:
                                return {'fsid': search_item, 'valid_id': False}

                        return body

            except asyncio.TimeoutError:
                logging.info("Timeout error for item: {} at {}. Retry {}".format(endpoint[1], endpoint[0], retry))
                retry += 1
                await asyncio.sleep(1)

            except aiohttp.ClientError as ex:
                logging.error("{} error while getting item: {} from {}".format(ex.__class__, endpoint[1], endpoint[0]))
                return {'search_item': endpoint[1]}

        logging.error("Timeout error after 5 retries for search_item: {} from {}".format(endpoint[1], endpoint[0]))
        return {'search_item': endpoint[1]}

    @staticmethod
    def _parse_rate_limit(headers):
        """Parses the rate limit form the header
        Args:
            headers (CIMultiDictProxy): The header returned from the response
        Returns:
            The rate limit information
        """
        return {'limit': headers.get('x-ratelimit-limit'), 'remaining': headers.get('x-ratelimit-remaining'),
                'reset': headers.get('x-ratelimit-reset'), 'requestId': headers.get('x-request-id')}

    @staticmethod
    def _network_error(options, rate_limit, error=None, status=None, message=None):
        """Handles any network errors as a result of the First Street Foundation API
        Args:
            options (dict): The options used in the header of the response
            rate_limit (dict): The rate limit information
            error (dict): The body returned from the request call
            status (str): The status error from the response
            message (str): The message error from the response
        Returns:
            A First Street error class
        """
        if error:
            status = int(error.get('code'))
            message = error.get('message')

        if not status == 429:
            formatted = "Network Error {}: {}".format(status, message)
        else:
            formatted = "Network Error {}: {}. Limit: {}. Remaining: {}. Reset: {}".format(status,
                                                                                           message,
                                                                                           rate_limit.get('limit'),
                                                                                           rate_limit.get('remaining'),
                                                                                           rate_limit.get('reset'))

        return {
            401: e.UnauthorizedError(message=formatted,
                                     attachments={"options": options, "rate_limit": rate_limit}),
            406: e.NotAcceptableError(message=formatted,
                                      attachments={"options": options, "rate_limit": rate_limit}),
            429: e.RateLimitError(message=formatted, attachments={"options": options, "rate_limit": rate_limit}),
            500: e.InternalError(message=formatted, attachments={"options": options, "rate_limit": rate_limit}),
            503: e.OfflineError(message=formatted, attachments={"options": options, "rate_limit": rate_limit}),
        }.get(status,
              e.UnknownError(message=formatted, attachments={"options": options, "rate_limit": rate_limit}))
