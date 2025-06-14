# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.
#
#  Licensed to Elasticsearch B.V. under one or more contributor
#  license agreements. See the NOTICE file distributed with
#  this work for additional information regarding copyright
#  ownership. Elasticsearch B.V. licenses this file to you under
#  the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.


from typing import Any
from unittest.mock import patch

from opensearchpy import TransportError, helpers
from opensearchpy.helpers import ScanError

from ...test_cases import SkipTest
from .. import OpenSearchTestCase


class FailingBulkClient:
    def __init__(
        self,
        client: Any,
        fail_at: Any = (2,),
        fail_with: Any = TransportError(599, "Error!", {}),
    ) -> None:
        self.client = client
        self._called = 0
        self._fail_at = fail_at
        self.transport = client.transport
        self._fail_with = fail_with

    def bulk(self, *args: Any, **kwargs: Any) -> Any:
        self._called += 1
        if self._called in self._fail_at:
            raise self._fail_with
        return self.client.bulk(*args, **kwargs)


class TestStreamingBulk(OpenSearchTestCase):
    def test_actions_remain_unchanged(self) -> None:
        actions = [{"_id": 1}, {"_id": 2}]
        for ok, _ in helpers.streaming_bulk(
            client=self.client, actions=actions, index="test-index"
        ):
            self.assertTrue(ok)
        self.assertEqual([{"_id": 1}, {"_id": 2}], actions)

    def test_all_documents_get_inserted(self) -> None:
        docs = [{"answer": x, "_id": x} for x in range(100)]
        for ok, _ in helpers.streaming_bulk(
            client=self.client, actions=docs, index="test-index", refresh=True
        ):
            self.assertTrue(ok)

        self.assertEqual(100, self.client.count(index="test-index")["count"])
        self.assertEqual(
            {"answer": 42}, self.client.get(index="test-index", id=42)["_source"]
        )

    def test_all_errors_from_chunk_are_raised_on_failure(self) -> None:
        self.client.indices.create(
            index="i",
            body={
                "mappings": {"properties": {"a": {"type": "integer"}}},
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            },
        )
        self.client.cluster.health(wait_for_status="yellow")

        try:
            for ok, _ in helpers.streaming_bulk(
                self.client, [{"a": "b"}, {"a": "c"}], index="i", raise_on_error=True
            ):
                self.assertTrue(ok)
        except helpers.errors.BulkIndexError as e:
            self.assertEqual(2, len(e.errors))
        else:
            assert False, "exception should have been raised"

    def test_different_op_types(self) -> Any:
        if self.opensearch_version() < (0, 90, 1):
            raise SkipTest("update supported since 0.90.1")
        self.client.index(index="i", id=45, body={})
        self.client.index(index="i", id=42, body={})
        docs = [
            {"_index": "i", "_id": 47, "f": "v"},
            {"_op_type": "delete", "_index": "i", "_id": 45},
            {
                "_op_type": "update",
                "_index": "i",
                "_id": 42,
                "doc": {"answer": 42},
            },
        ]
        for ok, _ in helpers.streaming_bulk(client=self.client, actions=docs):
            self.assertTrue(ok)

        self.assertFalse(self.client.exists(index="i", id=45))
        self.assertEqual({"answer": 42}, self.client.get(index="i", id=42)["_source"])
        self.assertEqual({"f": "v"}, self.client.get(index="i", id=47)["_source"])

    def test_transport_error_can_becaught(self) -> None:
        failing_client = FailingBulkClient(self.client)
        docs = [
            {"_index": "i", "_id": 47, "f": "v"},
            {"_index": "i", "_id": 45, "f": "v"},
            {"_index": "i", "_id": 42, "f": "v"},
        ]

        results = list(
            helpers.streaming_bulk(
                client=failing_client,
                actions=docs,
                raise_on_exception=False,
                raise_on_error=False,
                chunk_size=1,
            )
        )
        self.assertEqual(3, len(results))
        self.assertEqual([True, False, True], [r[0] for r in results])

        exc = results[1][1]["index"].pop("exception")
        self.assertIsInstance(exc, TransportError)
        self.assertEqual(599, exc.status_code)
        self.assertEqual(
            {
                "index": {
                    "_index": "i",
                    "_id": 45,
                    "data": {"f": "v"},
                    "error": "TransportError(599, 'Error!')",
                    "status": 599,
                }
            },
            results[1][1],
        )

    def test_rejected_documents_are_retried(self) -> None:
        failing_client = FailingBulkClient(
            self.client, fail_with=TransportError(429, "Rejected!", {})
        )
        docs = [
            {"_index": "i", "_id": 47, "f": "v"},
            {"_index": "i", "_id": 45, "f": "v"},
            {"_index": "i", "_id": 42, "f": "v"},
        ]
        results = list(
            helpers.streaming_bulk(
                client=failing_client,
                actions=docs,
                raise_on_exception=False,
                raise_on_error=False,
                chunk_size=1,
                max_retries=1,
                initial_backoff=0,
            )
        )
        self.assertEqual(3, len(results))
        self.assertEqual([True, True, True], [r[0] for r in results])
        self.client.indices.refresh(index="i")
        res = self.client.search(index="i")
        self.assertEqual({"value": 3, "relation": "eq"}, res["hits"]["total"])
        self.assertEqual(4, failing_client._called)

    def test_rejected_documents_are_retried_at_most_max_retries_times(self) -> None:
        failing_client = FailingBulkClient(
            self.client, fail_at=(1, 2), fail_with=TransportError(429, "Rejected!", {})
        )

        docs = [
            {"_index": "i", "_id": 47, "f": "v"},
            {"_index": "i", "_id": 45, "f": "v"},
            {"_index": "i", "_id": 42, "f": "v"},
        ]
        results = list(
            helpers.streaming_bulk(
                client=failing_client,
                actions=docs,
                raise_on_exception=False,
                raise_on_error=False,
                chunk_size=1,
                max_retries=1,
                initial_backoff=0,
            )
        )
        self.assertEqual(3, len(results))
        self.assertEqual([False, True, True], [r[0] for r in results])
        self.client.indices.refresh(index="i")
        res = self.client.search(index="i")
        self.assertEqual({"value": 2, "relation": "eq"}, res["hits"]["total"])
        self.assertEqual(4, failing_client._called)

    def test_transport_error_is_raised_with_max_retries(self) -> None:
        failing_client = FailingBulkClient(
            self.client,
            fail_at=(1, 2, 3, 4),
            fail_with=TransportError(429, "Rejected!", {}),
        )

        def streaming_bulk() -> Any:
            results = list(
                helpers.streaming_bulk(
                    failing_client,
                    [{"a": 42}, {"a": 39}],
                    raise_on_exception=True,
                    max_retries=3,
                    initial_backoff=0,
                )
            )
            return results

        self.assertRaises(TransportError, streaming_bulk)
        self.assertEqual(4, failing_client._called)


class TestBulk(OpenSearchTestCase):
    def test_bulk_works_with_single_item(self) -> None:
        docs = [{"answer": 42, "_id": 1}]
        success, failed = helpers.bulk(
            client=self.client, actions=docs, index="test-index", refresh=True
        )

        self.assertEqual(1, success)
        self.assertFalse(failed)
        self.assertEqual(1, self.client.count(index="test-index")["count"])
        self.assertEqual(
            {"answer": 42}, self.client.get(index="test-index", id=1)["_source"]
        )

    def test_all_documents_get_inserted(self) -> None:
        docs = [{"answer": x, "_id": x} for x in range(100)]
        success, failed = helpers.bulk(
            client=self.client, actions=docs, index="test-index", refresh=True
        )

        self.assertEqual(100, success)
        self.assertFalse(failed)
        self.assertEqual(100, self.client.count(index="test-index")["count"])
        self.assertEqual(
            {"answer": 42}, self.client.get(index="test-index", id=42)["_source"]
        )

    def test_stats_only_reports_numbers(self) -> None:
        docs = [{"answer": x} for x in range(100)]
        success, failed = helpers.bulk(
            client=self.client,
            actions=docs,
            index="test-index",
            refresh=True,
            stats_only=True,
        )

        self.assertEqual(100, success)
        self.assertEqual(0, failed)
        self.assertEqual(100, self.client.count(index="test-index")["count"])

    def test_errors_are_reported_correctly(self) -> None:
        self.client.indices.create(
            index="i",
            body={
                "mappings": {"properties": {"a": {"type": "integer"}}},
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            },
        )
        self.client.cluster.health(wait_for_status="yellow")

        success, failed = helpers.bulk(
            client=self.client,
            actions=[{"a": 42}, {"a": "c", "_id": 42}],
            index="i",
            raise_on_error=False,
        )
        self.assertEqual(1, success)
        self.assertEqual(1, len(failed))
        error = failed[0]
        self.assertEqual("42", error["index"]["_id"])
        self.assertEqual("i", error["index"]["_index"])
        print(error["index"]["error"])
        self.assertTrue(
            "MapperParsingException" in repr(error["index"]["error"])
            or "mapper_parsing_exception" in repr(error["index"]["error"])
        )

    def test_error_is_raised(self) -> None:
        self.client.indices.create(
            index="i",
            body={
                "mappings": {"properties": {"a": {"type": "integer"}}},
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            },
        )
        self.client.cluster.health(wait_for_status="yellow")

        self.assertRaises(
            helpers.errors.BulkIndexError,
            helpers.bulk,
            self.client,
            [{"a": 42}, {"a": "c"}],
            index="i",
        )

    def test_ignore_error_if_raised(self) -> None:
        # ignore the status code 400 in tuple
        helpers.bulk(
            client=self.client,
            actions=[{"a": 42}, {"a": "c"}],
            index="i",
            ignore_status=(400,),
        )

        # ignore the status code 400 in list
        helpers.bulk(
            client=self.client,
            actions=[{"a": 42}, {"a": "c"}],
            index="i",
            ignore_status=[
                400,
            ],
        )

        # ignore the status code 400
        helpers.bulk(
            client=self.client,
            actions=[{"a": 42}, {"a": "c"}],
            index="i",
            ignore_status=400,
        )

        # ignore only the status code in the `ignore_status` argument
        self.assertRaises(
            helpers.errors.BulkIndexError,
            helpers.bulk,
            self.client,
            [{"a": 42}, {"a": "c"}],
            index="i",
            ignore_status=(444,),
        )

        # ignore transport error exception
        failing_client = FailingBulkClient(self.client)
        helpers.bulk(
            client=failing_client, actions=[{"a": 42}], index="i", ignore_status=(599,)
        )

    def test_errors_are_collected_properly(self) -> None:
        self.client.indices.create(
            index="i",
            body={
                "mappings": {"properties": {"a": {"type": "integer"}}},
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            },
        )
        self.client.cluster.health(wait_for_status="yellow")

        success, failed = helpers.bulk(
            client=self.client,
            actions=[{"a": 42}, {"a": "c"}],
            index="i",
            stats_only=True,
            raise_on_error=False,
        )
        self.assertEqual(1, success)
        self.assertEqual(1, failed)


class TestScan(OpenSearchTestCase):
    mock_scroll_responses = [
        {
            "_scroll_id": "dummy_id",
            "_shards": {"successful": 4, "total": 5, "skipped": 0},
            "hits": {"hits": [{"scroll_data": 42}]},
        },
        {
            "_scroll_id": "dummy_id",
            "_shards": {"successful": 4, "total": 5, "skipped": 0},
            "hits": {"hits": []},
        },
    ]

    def teardown_method(self, m: Any) -> None:
        self.client.transport.perform_request("DELETE", "/_search/scroll/_all")
        super().teardown_method(m)

    def test_order_can_be_preserved(self) -> None:
        bulk: Any = []
        for x in range(100):
            bulk.append({"index": {"_index": "test_index", "_id": x}})
            bulk.append({"answer": x, "correct": x == 42})
        self.client.bulk(body=bulk, refresh=True)

        docs = list(
            helpers.scan(
                self.client,
                index="test_index",
                query={"sort": "answer"},
                preserve_order=True,
            )
        )

        self.assertEqual(100, len(docs))
        self.assertEqual(list(map(str, range(100))), list(d["_id"] for d in docs))
        self.assertEqual(list(range(100)), list(d["_source"]["answer"] for d in docs))

    def test_all_documents_are_read(self) -> None:
        bulk: Any = []
        for x in range(100):
            bulk.append({"index": {"_index": "test_index", "_id": x}})
            bulk.append({"answer": x, "correct": x == 42})
        self.client.bulk(body=bulk, refresh=True)

        docs = list(helpers.scan(self.client, index="test_index", size=2))

        self.assertEqual(100, len(docs))
        self.assertEqual(set(map(str, range(100))), {d["_id"] for d in docs})
        self.assertEqual(set(range(100)), {d["_source"]["answer"] for d in docs})

    def test_scroll_error(self) -> None:
        bulk: Any = []
        for x in range(4):
            bulk.append({"index": {"_index": "test_index"}})
            bulk.append({"value": x})
        self.client.bulk(body=bulk, refresh=True)

        with patch.object(self.client, "scroll") as scroll_mock:
            scroll_mock.side_effect = self.mock_scroll_responses
            data = list(
                helpers.scan(
                    self.client,
                    index="test_index",
                    size=2,
                    raise_on_error=False,
                    clear_scroll=False,
                )
            )
            self.assertEqual(len(data), 3)
            self.assertEqual(data[-1], {"scroll_data": 42})

            scroll_mock.side_effect = self.mock_scroll_responses
            with self.assertRaises(ScanError):
                data = list(
                    helpers.scan(
                        self.client,
                        index="test_index",
                        size=2,
                        raise_on_error=True,
                        clear_scroll=False,
                    )
                )
            self.assertEqual(len(data), 3)
            self.assertEqual(data[-1], {"scroll_data": 42})

    def test_initial_search_error(self) -> None:
        with patch.object(self, "client") as client_mock:
            client_mock.search.return_value = {
                "_scroll_id": "dummy_id",
                "_shards": {"successful": 4, "total": 5, "skipped": 0},
                "hits": {"hits": [{"search_data": 1}]},
            }
            client_mock.scroll.side_effect = self.mock_scroll_responses

            data = list(
                helpers.scan(
                    self.client, index="test_index", size=2, raise_on_error=False
                )
            )
            self.assertEqual(data, [{"search_data": 1}, {"scroll_data": 42}])

            client_mock.scroll.side_effect = self.mock_scroll_responses
            with self.assertRaises(ScanError):
                data = list(
                    helpers.scan(
                        self.client, index="test_index", size=2, raise_on_error=True
                    )
                )
                self.assertEqual(data, [{"search_data": 1}])
                client_mock.scroll.assert_not_called()

    def test_no_scroll_id_fast_route(self) -> None:
        with patch.object(self, "client") as client_mock:
            client_mock.search.return_value = {"no": "_scroll_id"}
            data = list(helpers.scan(self.client, index="test_index"))

            self.assertEqual(data, [])
            client_mock.scroll.assert_not_called()
            client_mock.clear_scroll.assert_not_called()

    def test_scan_auth_kwargs_forwarded(self) -> None:
        for key, val in {
            "api_key": ("name", "value"),
            "http_auth": ("username", "password"),
            "headers": {"custom": "header"},
        }.items():
            with patch.object(self, "client") as client_mock:
                client_mock.search.return_value = {
                    "_scroll_id": "scroll_id",
                    "_shards": {"successful": 5, "total": 5, "skipped": 0},
                    "hits": {"hits": [{"search_data": 1}]},
                }
                client_mock.scroll.return_value = {
                    "_scroll_id": "scroll_id",
                    "_shards": {"successful": 5, "total": 5, "skipped": 0},
                    "hits": {"hits": []},
                }
                client_mock.clear_scroll.return_value = {}

                data = list(
                    helpers.scan(self.client, index="test_index", **{key: val})  # type: ignore
                )

                self.assertEqual(data, [{"search_data": 1}])

                # Assert that 'search', 'scroll' and 'clear_scroll' all
                # received the extra kwarg related to authentication.
                for api_mock in (
                    client_mock.search,
                    client_mock.scroll,
                    client_mock.clear_scroll,
                ):
                    self.assertEqual(api_mock.call_args[1][key], val)

    def test_scan_auth_kwargs_favor_scroll_kwargs_option(self) -> None:
        with patch.object(self, "client") as client_mock:
            client_mock.search.return_value = {
                "_scroll_id": "scroll_id",
                "_shards": {"successful": 5, "total": 5, "skipped": 0},
                "hits": {"hits": [{"search_data": 1}]},
            }
            client_mock.scroll.return_value = {
                "_scroll_id": "scroll_id",
                "_shards": {"successful": 5, "total": 5, "skipped": 0},
                "hits": {"hits": []},
            }
            client_mock.clear_scroll.return_value = {}

            data = list(
                helpers.scan(
                    self.client,
                    index="test_index",
                    scroll_kwargs={"headers": {"scroll": "kwargs"}, "sort": "asc"},
                    headers={"not scroll": "kwargs"},
                )
            )

            self.assertEqual(data, [{"search_data": 1}])

            # Assert that we see 'scroll_kwargs' options used instead of 'kwargs'
            self.assertEqual(
                client_mock.scroll.call_args[1]["headers"], {"scroll": "kwargs"}
            )
            self.assertEqual(client_mock.scroll.call_args[1]["sort"], "asc")

    @patch("opensearchpy.helpers.actions.logger")
    def test_logger(self, logger_mock: Any) -> None:
        bulk: Any = []
        for x in range(4):
            bulk.append({"index": {"_index": "test_index"}})
            bulk.append({"value": x})
        self.client.bulk(body=bulk, refresh=True)

        with patch.object(self.client, "scroll") as scroll_mock:
            scroll_mock.side_effect = self.mock_scroll_responses
            list(
                helpers.scan(
                    self.client,
                    index="test_index",
                    size=2,
                    raise_on_error=False,
                    clear_scroll=False,
                )
            )
            logger_mock.warning.assert_called()

            scroll_mock.side_effect = self.mock_scroll_responses
            try:
                list(
                    helpers.scan(
                        self.client,
                        index="test_index",
                        size=2,
                        raise_on_error=True,
                        clear_scroll=False,
                    )
                )
            except ScanError:
                pass
            logger_mock.warning.assert_called()

    def test_clear_scroll(self) -> None:
        bulk: Any = []
        for x in range(4):
            bulk.append({"index": {"_index": "test_index"}})
            bulk.append({"value": x})
        self.client.bulk(body=bulk, refresh=True)

        with patch.object(
            self.client, "clear_scroll", wraps=self.client.clear_scroll
        ) as spy:
            list(helpers.scan(self.client, index="test_index", size=2))
            spy.assert_called_once()

            spy.reset_mock()
            list(
                helpers.scan(self.client, index="test_index", size=2, clear_scroll=True)
            )
            spy.assert_called_once()

            spy.reset_mock()
            list(
                helpers.scan(
                    self.client, index="test_index", size=2, clear_scroll=False
                )
            )
            spy.assert_not_called()

    def test_shards_no_skipped_field(self) -> None:
        with patch.object(self, "client") as client_mock:
            client_mock.search.return_value = {
                "_scroll_id": "dummy_id",
                "_shards": {"successful": 5, "total": 5},
                "hits": {"hits": [{"search_data": 1}]},
            }
            client_mock.scroll.side_effect = [
                {
                    "_scroll_id": "dummy_id",
                    "_shards": {"successful": 5, "total": 5},
                    "hits": {"hits": [{"scroll_data": 42}]},
                },
                {
                    "_scroll_id": "dummy_id",
                    "_shards": {"successful": 5, "total": 5},
                    "hits": {"hits": []},
                },
            ]

            data = list(
                helpers.scan(
                    self.client, index="test_index", size=2, raise_on_error=True
                )
            )
            self.assertEqual(data, [{"search_data": 1}, {"scroll_data": 42}])


class TestReindex(OpenSearchTestCase):
    def setup_method(self, _: Any) -> None:
        bulk: Any = []
        for x in range(100):
            bulk.append({"index": {"_index": "test_index", "_id": x}})
            bulk.append(
                {
                    "answer": x,
                    "correct": x == 42,
                    "type": "answers" if x % 2 == 0 else "questions",
                }
            )
        self.client.bulk(body=bulk, refresh=True)

    def test_reindex_passes_kwargs_to_scan_and_bulk(self) -> None:
        helpers.reindex(
            client=self.client,
            source_index="test_index",
            target_index="prod_index",
            scan_kwargs={"q": "type:answers"},
            bulk_kwargs={"refresh": True},
        )

        self.assertTrue(self.client.indices.exists(index="prod_index"))
        self.assertEqual(
            50, self.client.count(index="prod_index", q="type:answers")["count"]
        )

        self.assertEqual(
            {"answer": 42, "correct": True, "type": "answers"},
            self.client.get(index="prod_index", id=42)["_source"],
        )

    def test_reindex_accepts_a_query(self) -> None:
        helpers.reindex(
            client=self.client,
            source_index="test_index",
            target_index="prod_index",
            query={"query": {"bool": {"filter": {"term": {"type": "answers"}}}}},
        )
        self.client.indices.refresh()

        self.assertTrue(self.client.indices.exists(index="prod_index"))
        self.assertEqual(
            50, self.client.count(index="prod_index", q="type:answers")["count"]
        )

        self.assertEqual(
            {"answer": 42, "correct": True, "type": "answers"},
            self.client.get(index="prod_index", id=42)["_source"],
        )

    def test_all_documents_get_moved(self) -> None:
        helpers.reindex(
            client=self.client, source_index="test_index", target_index="prod_index"
        )
        self.client.indices.refresh()

        self.assertTrue(self.client.indices.exists(index="prod_index"))
        self.assertEqual(
            50, self.client.count(index="prod_index", q="type:questions")["count"]
        )
        self.assertEqual(
            50, self.client.count(index="prod_index", q="type:answers")["count"]
        )

        self.assertEqual(
            {"answer": 42, "correct": True, "type": "answers"},
            self.client.get(index="prod_index", id=42)["_source"],
        )


class TestParentChildReindex(OpenSearchTestCase):
    def setup_method(self, _: Any) -> None:
        body = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "question_answer": {
                        "type": "join",
                        "relations": {"question": "answer"},
                    }
                }
            },
        }
        self.client.indices.create(index="test-index", body=body)
        self.client.indices.create(index="real-index", body=body)

        self.client.index(
            index="test-index", id=42, body={"question_answer": "question"}
        )
        self.client.index(
            index="test-index",
            id=47,
            routing=42,
            body={"some": "data", "question_answer": {"name": "answer", "parent": 42}},
        )
        self.client.indices.refresh(index="test-index")

    def test_children_are_reindexed_correctly(self) -> None:
        helpers.reindex(
            client=self.client, source_index="test-index", target_index="real-index"
        )

        self.assertEqual(
            {"question_answer": "question"},
            self.client.get(index="real-index", id=42)["_source"],
        )

        self.assertEqual(
            {"some": "data", "question_answer": {"name": "answer", "parent": 42}},
            self.client.get(index="test-index", id=47, routing=42)["_source"],
        )
