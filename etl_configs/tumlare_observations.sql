SELECT
    observations.id,
    observation_date,
    animal_condition,
    time_start,
    time_end,
    latitude,
    longitude,
    distance_min,
    distance_max,
    quantity_min,
    quantity_max,
    quantity_cubs_min,
    quantity_cubs_max,
    quantity_dead,
    dead_length_min,
    observer_comment,
    observations.updated_at,
    counties.name,
    animal_decomposion,
    (SELECT GROUP_CONCAT(filename SEPARATOR ',')
        FROM images
        WHERE public IS TRUE AND observation = observations.id) AS associatedMedia
FROM
    observations
LEFT JOIN
    counties
ON
    observations.county = counties.id
WHERE
    observations.record_approved = TRUE
