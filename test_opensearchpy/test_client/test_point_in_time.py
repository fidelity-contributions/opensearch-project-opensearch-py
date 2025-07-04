# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

from test_opensearchpy.test_cases import OpenSearchTestCase


class TestPointInTime(OpenSearchTestCase):
    def test_create_pit(self) -> None:
        index_name = "test-index"
        self.client.create_pit(index=index_name)
        self.assert_url_called("POST", "/test-index/_search/point_in_time")

    def test_delete_pit(self) -> None:
        self.client.delete_pit(body={"pit_id": ["Sample-PIT-ID"]})
        self.assert_url_called("DELETE", "/_search/point_in_time")

    def test_delete_all_pits(self) -> None:
        self.client.delete_all_pits()
        self.assert_url_called("DELETE", "/_search/point_in_time/_all")

    def test_get_all_pits(self) -> None:
        self.client.get_all_pits()
        self.assert_url_called("GET", "/_search/point_in_time/_all")
