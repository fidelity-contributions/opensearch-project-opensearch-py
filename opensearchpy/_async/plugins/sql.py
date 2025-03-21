# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

# ------------------------------------------------------------------------------------------
# THIS CODE IS AUTOMATICALLY GENERATED AND MANUAL EDITS WILL BE LOST
#
# To contribute, kindly make modifications in the opensearch-py client generator
# or in the OpenSearch API specification, and run `nox -rs generate`. See DEVELOPER_GUIDE.md
# and https://github.com/opensearch-project/opensearch-api-specification for details.
# -----------------------------------------------------------------------------------------+


from typing import Any

from ..client.utils import NamespacedClient, query_params


class SqlClient(NamespacedClient):
    @query_params(
        "error_trace", "filter_path", "format", "human", "pretty", "sanitize", "source"
    )
    async def close(
        self,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Clear the cursor context.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg sanitize: Specifies whether to escape special characters in
            the results Default is True.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "POST", "/_plugins/_sql/close", params=params, headers=headers, body=body
        )

    @query_params(
        "error_trace", "filter_path", "format", "human", "pretty", "sanitize", "source"
    )
    async def explain(
        self,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Shows how a query is executed against OpenSearch.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg sanitize: Specifies whether to escape special characters in
            the results Default is True.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "POST", "/_plugins/_sql/_explain", params=params, headers=headers, body=body
        )

    @query_params(
        "error_trace", "filter_path", "format", "human", "pretty", "sanitize", "source"
    )
    async def get_stats(
        self,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Collect metrics for the plugin within the interval.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg sanitize: Specifies whether to escape special characters in
            the results Default is True.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "GET", "/_plugins/_sql/stats", params=params, headers=headers
        )

    @query_params(
        "error_trace", "filter_path", "format", "human", "pretty", "sanitize", "source"
    )
    async def post_stats(
        self,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        By a stats endpoint, you are able to collect metrics for the plugin within the
        interval.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg sanitize: Specifies whether to escape special characters in
            the results Default is True.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "POST", "/_plugins/_sql/stats", params=params, headers=headers, body=body
        )

    @query_params(
        "error_trace", "filter_path", "format", "human", "pretty", "sanitize", "source"
    )
    async def query(
        self,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Send a SQL/PPL query to the SQL plugin.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg sanitize: Specifies whether to escape special characters in
            the results Default is True.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "POST", "/_plugins/_sql", params=params, headers=headers, body=body
        )

    @query_params("error_trace", "filter_path", "format", "human", "pretty", "source")
    async def settings(
        self,
        body: Any = None,
        params: Any = None,
        headers: Any = None,
    ) -> Any:
        """
        Adds SQL settings to the standard OpenSearch cluster settings.


        :arg error_trace: Whether to include the stack trace of returned
            errors. Default is false.
        :arg filter_path: Used to reduce the response. This parameter
            takes a comma-separated list of filters. It supports using wildcards to
            match any field or part of a field’s name. You can also exclude fields
            with "-".
        :arg format: A short version of the Accept header (for example,
            `json`, `yaml`).
        :arg human: Whether to return human readable values for
            statistics. Default is True.
        :arg pretty: Whether to pretty format the returned JSON
            response. Default is false.
        :arg source: The URL-encoded request definition. Useful for
            libraries that do not accept a request body for non-POST requests.
        """
        return await self.transport.perform_request(
            "PUT",
            "/_plugins/_query/settings",
            params=params,
            headers=headers,
            body=body,
        )
