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

import base64
from datetime import datetime
from ipaddress import ip_address
from typing import Any

import pytest
from dateutil import tz

from opensearchpy import InnerDoc, Range, ValidationException
from opensearchpy.helpers import field
from opensearchpy.helpers.index import Index
from opensearchpy.helpers.mapping import Mapping
from opensearchpy.helpers.test import OpenSearchTestCase


def test_date_range_deserialization() -> None:
    data = {"lt": "2018-01-01T00:30:10"}

    r = field.DateRange().deserialize(data)

    assert isinstance(r, Range)
    assert r.lt == datetime(2018, 1, 1, 0, 30, 10)


def test_boolean_deserialization() -> None:
    bf = field.Boolean()

    assert not bf.deserialize("false")
    assert not bf.deserialize(False)
    assert not bf.deserialize("")
    assert not bf.deserialize(0)

    assert bf.deserialize(True)
    assert bf.deserialize("true")
    assert bf.deserialize(1)


def test_date_field_can_have_default_tz() -> None:
    f: Any = field.Date(default_timezone="UTC")
    now = datetime.now()

    now_with_tz = f._deserialize(now)

    assert now_with_tz.tzinfo == tz.gettz("UTC")
    assert now.isoformat() + "+00:00" == now_with_tz.isoformat()

    now_with_tz = f._deserialize(now.isoformat())

    assert now_with_tz.tzinfo == tz.gettz("UTC")
    assert now.isoformat() + "+00:00" == now_with_tz.isoformat()


def test_custom_field_car_wrap_other_field() -> None:
    class MyField(field.CustomField):
        @property
        def builtin_type(self) -> Any:
            return field.Text(**self._params)

    assert {"type": "text", "index": "not_analyzed"} == MyField(
        index="not_analyzed"
    ).to_dict()


def test_field_from_dict() -> None:
    f = field.construct_field({"type": "text", "index": "not_analyzed"})

    assert isinstance(f, field.Text)
    assert {"type": "text", "index": "not_analyzed"} == f.to_dict()


def test_multi_fields_are_accepted_and_parsed() -> None:
    f = field.construct_field(
        "text",
        fields={"raw": {"type": "keyword"}, "eng": field.Text(analyzer="english")},
    )

    assert isinstance(f, field.Text)
    assert {
        "type": "text",
        "fields": {
            "raw": {"type": "keyword"},
            "eng": {"type": "text", "analyzer": "english"},
        },
    } == f.to_dict()


def test_nested_provides_direct_access_to_its_fields() -> None:
    f = field.Nested(properties={"name": {"type": "text", "index": "not_analyzed"}})

    assert "name" in f
    assert f["name"] == field.Text(index="not_analyzed")


def test_field_supports_multiple_analyzers() -> None:
    f = field.Text(analyzer="snowball", search_analyzer="keyword")
    assert {
        "analyzer": "snowball",
        "search_analyzer": "keyword",
        "type": "text",
    } == f.to_dict()


def test_multifield_supports_multiple_analyzers() -> None:
    f = field.Text(
        fields={
            "f1": field.Text(search_analyzer="keyword", analyzer="snowball"),
            "f2": field.Text(analyzer="keyword"),
        }
    )
    assert {
        "fields": {
            "f1": {
                "analyzer": "snowball",
                "search_analyzer": "keyword",
                "type": "text",
            },
            "f2": {"analyzer": "keyword", "type": "text"},
        },
        "type": "text",
    } == f.to_dict()


def test_scaled_float() -> None:
    with pytest.raises(TypeError):
        field.ScaledFloat()  # type: ignore
    f: Any = field.ScaledFloat(scaling_factor=123)
    assert f.to_dict() == {"scaling_factor": 123, "type": "scaled_float"}


def test_ipaddress() -> None:
    f = field.Ip()
    assert f.deserialize("127.0.0.1") == ip_address("127.0.0.1")
    assert f.deserialize("::1") == ip_address("::1")
    assert f.serialize(f.deserialize("::1")) == "::1"
    assert f.deserialize(None) is None
    with pytest.raises(ValueError):
        assert f.deserialize("not_an_ipaddress")


def test_float() -> None:
    f = field.Float()
    assert f.deserialize("42") == 42.0
    assert f.deserialize(None) is None
    with pytest.raises(ValueError):
        assert f.deserialize("not_a_float")


def test_integer() -> None:
    f = field.Integer()
    assert f.deserialize("42") == 42
    assert f.deserialize(None) is None
    with pytest.raises(ValueError):
        assert f.deserialize("not_an_integer")


def test_binary() -> None:
    f = field.Binary()
    assert f.deserialize(base64.b64encode(b"42")) == b"42"
    assert f.deserialize(f.serialize(b"42")) == b"42"
    assert f.deserialize(None) is None


def test_constant_keyword() -> None:
    f = field.ConstantKeyword()
    assert f.to_dict() == {"type": "constant_keyword"}


def test_rank_features() -> None:
    f = field.RankFeatures()
    assert f.to_dict() == {"type": "rank_features"}


def test_object_dynamic_values() -> None:
    for dynamic in True, False, "strict":
        f = field.Object(dynamic=dynamic)
        assert f.to_dict()["dynamic"] == dynamic


def test_object_disabled() -> None:
    f = field.Object(enabled=False)
    assert f.to_dict() == {"type": "object", "enabled": False}


def test_object_constructor() -> None:
    expected = {"type": "object", "properties": {"inner_int": {"type": "integer"}}}

    class Inner(InnerDoc):
        inner_int = field.Integer()

    obj_from_doc = field.Object(doc_class=Inner)
    assert obj_from_doc.to_dict() == expected

    obj_from_props = field.Object(properties={"inner_int": field.Integer()})
    assert obj_from_props.to_dict() == expected

    with pytest.raises(ValidationException):
        field.Object(doc_class=Inner, properties={"inner_int": field.Integer()})

    with pytest.raises(ValidationException):
        field.Object(doc_class=Inner, dynamic=False)


def test_knn_vector() -> None:
    f = field.KnnVector(dimension=128)
    assert f.to_dict() == {"type": "knn_vector", "dimension": 128}

    # Test that dimension parameter is required
    with pytest.raises(TypeError):
        field.KnnVector()  # type: ignore

    assert f._multi is True


def test_knn_vector_with_additional_params() -> None:
    f = field.KnnVector(
        dimension=256, method={"name": "hnsw", "space_type": "l2", "engine": "faiss"}
    )
    expected = {
        "type": "knn_vector",
        "dimension": 256,
        "method": {"name": "hnsw", "space_type": "l2", "engine": "faiss"},
    }
    assert f.to_dict() == expected


def test_knn_vector_serialization() -> None:
    f = field.KnnVector(dimension=3)

    vector_data = [1.0, 2.0, 3.0]
    serialized = f.serialize(vector_data)
    assert serialized == vector_data

    assert f.serialize(None) is None


def test_knn_vector_deserialization() -> None:
    f = field.KnnVector(dimension=3)

    vector_data = [1.0, 2.0, 3.0]
    deserialized = f.deserialize(vector_data)
    assert deserialized == vector_data

    assert f.deserialize(None) is None


def test_knn_vector_construct_from_dict() -> None:
    f = field.construct_field({"type": "knn_vector", "dimension": 128})

    assert isinstance(f, field.KnnVector)
    assert f.to_dict() == {"type": "knn_vector", "dimension": 128}


def test_knn_vector_construct_from_dict_with_method() -> None:
    f = field.construct_field(
        {
            "type": "knn_vector",
            "dimension": 256,
            "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"},
        }
    )

    assert isinstance(f, field.KnnVector)
    expected = {
        "type": "knn_vector",
        "dimension": 256,
        "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"},
    }
    assert f.to_dict() == expected


class TestKnnVectorIntegration(OpenSearchTestCase):
    def test_index_and_retrieve_knn_vector(self) -> None:
        index_name = "itest-knn-vector"
        # ensure clean state
        self.client.indices.delete(index=index_name, ignore=404)

        # Create index using DSL abstractions
        idx = Index(index_name, using=self.client)
        idx.settings(**{"index.knn": True})

        mapping = Mapping()
        mapping.field("vec", field.KnnVector(dimension=3))
        idx.mapping(mapping)

        result = idx.create()
        assert result["acknowledged"] is True

        field_mapping = idx.get_field_mapping(fields="vec")
        assert field_mapping[index_name]["mappings"]["vec"]["mapping"]["vec"] == {
            "type": "knn_vector",
            "dimension": 3,
        }

        # search tests
        doc = {"vec": [1.0, 2.0, 3.0]}
        result = self.client.index(index=index_name, id=1, body=doc, refresh=True)
        assert result["_shards"]["successful"] == 1
        get_resp = self.client.get(index=index_name, id=1)
        assert get_resp["_source"]["vec"] == doc["vec"]

        search_body = {
            "size": 1,
            "query": {"knn": {"vec": {"vector": [1.0, 2.0, 3.0], "k": 1}}},
        }
        search_resp = self.client.search(index=index_name, body=search_body)
        hits = search_resp["hits"]["hits"]
        assert len(hits) == 1
        assert hits[0]["_id"] == "1"

        # cleanup
        self.client.indices.delete(index=index_name)
