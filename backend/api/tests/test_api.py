def test_get_routes(client, mock_db, mock_auth):
    # Mock DB response
    mock_db.fetchall.return_value = []

    response = client.get("/routes")
    assert response.status_code == 200
    assert response.json() == {"routes": []}


def test_create_route(client, mock_db, mock_auth):
    mock_db.fetchone.return_value = [123]

    response = client.post(
        "/routes",
        json={
            "name": "Home to Work",
            "start_station_id": "7000",
            "end_station_id": "7001",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"route_id": 123}
