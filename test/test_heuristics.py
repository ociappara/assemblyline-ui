
import random

import pytest

from base import HOST, login_session, get_api_data

from assemblyline.common import forge
from assemblyline.odm.random_data import create_users, wipe_users, create_heuristics, wipe_heuristics

config = forge.get_config()
ds = forge.get_datastore(config)


def purge_heuristic():
    wipe_users(ds)
    wipe_heuristics(ds)


@pytest.fixture(scope="module")
def datastore(request):
    create_users(ds)
    create_heuristics(ds)
    request.addfinalizer(purge_heuristic)
    return ds


def test_get_heuristics(datastore, login_session):
    _, session = login_session

    heuristic = random.choice(datastore.heuristic.search("id:*", rows=100, as_obj=False)['items'])
    resp = get_api_data(session, f"{HOST}/api/v4/heuristics/{heuristic['heur_id']}/")
    assert resp['classification'] == heuristic['classification']
    assert resp['description'] == heuristic['description']
    assert resp['filetype'] == heuristic['filetype']
    assert resp['heur_id'] == heuristic['heur_id']
    assert resp['name'] == heuristic['name']


def test_heuristic_stats(datastore, login_session):
    _, session = login_session

    heuristic_count = datastore.heuristic.search("id:*", rows=0)['total']
    resp = get_api_data(session, f"{HOST}/api/v4/heuristics/stats/")
    assert len(resp) == heuristic_count
    for sig_stat in resp:
        assert sorted(list(sig_stat.keys())) == ['avg', 'classification', 'count', 'heur_id', 'max', 'min']