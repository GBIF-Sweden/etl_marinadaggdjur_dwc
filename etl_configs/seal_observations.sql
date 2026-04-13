SELECT
	seal_observations.id,
	observation_date,
	seal_type,
	latitude,
	longitude,
	quantity,
	length,
	counties.name as county,
	decayvalues.name as animal_decomposition_state,
	updated_at,
	(
	SELECT
		GROUP_CONCAT(filename SEPARATOR ' , ')
	FROM
		seal_images
	WHERE
		public IS TRUE
		AND sealobservation = seal_observations.id) AS associatedMedia
FROM
	seal_observations
LEFT JOIN counties ON
	seal_observations.county = counties.id
LEFT JOIN decayvalues ON
	seal_observations.animal_decomposion = decayvalues.id
WHERE
	seal_observations.record_approved = TRUE;
