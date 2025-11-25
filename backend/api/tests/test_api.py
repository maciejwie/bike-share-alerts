def test_get_routes(client, mock_db, mock_auth):
    # Mock DB response
    mock_cursor, _ = mock_db
    mock_cursor.fetchall.return_value = []

    response = client.get("/routes")
    assert response.status_code == 200
    assert response.json() == {"routes": []}


def test_create_route(client, mock_db, mock_auth):
    # First call checks for existing route (returns None)
    # Second call creates new route
    mock_cursor, _ = mock_db
    mock_cursor.fetchone.side_effect = [None, [123]]

    response = client.post(
        "/routes",
        json={
            "name": "Home to Work",
            "start_station_ids": [7000, 7002],
            "end_station_ids": [7001, 7003],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["route_id"] == 123
    assert data["existed"] is False


def test_create_route_idempotent(client, mock_db, mock_auth):
    # Mock existing route found
    mock_cursor, _ = mock_db
    mock_cursor.fetchone.return_value = [456]

    response = client.post(
        "/routes",
        json={
            "name": "Existing Route",
            "start_station_ids": [7000],
            "end_station_ids": [7001],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["route_id"] == 456
    assert data["existed"] is True


def test_create_route_validation_empty_stations(client, mock_db, mock_auth):
    response = client.post(
        "/routes",
        json={
            "name": "Invalid Route",
            "start_station_ids": [],
            "end_station_ids": [7001],
        },
    )
    assert response.status_code == 422
    assert "Must provide at least one station ID" in response.text


def test_create_route_validation_duplicate_stations(client, mock_db, mock_auth):
    response = client.post(
        "/routes",
        json={
            "name": "Invalid Route",
            "start_station_ids": [7000, 7000],
            "end_station_ids": [7001],
        },
    )
    assert response.status_code == 422
    assert "Station IDs must be unique" in response.text


def test_create_route_validation_invalid_days(client, mock_db, mock_auth):
    response = client.post(
        "/routes",
        json={
            "name": "Invalid Route",
            "start_station_ids": [7000],
            "end_station_ids": [7001],
            "days_of_week": [0, 7],  # 7 is invalid
        },
    )
    assert response.status_code == 422
    assert "Days of week must be 0-6" in response.text


def test_delete_route(client, mock_db, mock_auth):
    mock_cursor, _ = mock_db
    mock_cursor.rowcount = 1

    response = client.delete("/routes/some-uuid")
    assert response.status_code == 204


def test_delete_route_not_found(client, mock_db, mock_auth):
    mock_cursor, _ = mock_db
    mock_cursor.rowcount = 0

    response = client.delete("/routes/nonexistent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"
