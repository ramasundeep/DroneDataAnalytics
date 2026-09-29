// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Geodetic <-> local tangent-plane conversion about an area origin.
//
// APPROXIMATION (documented on purpose — "boring over clever"):
// flat-earth / equirectangular projection about the origin:
//
//   North_m = R * (lat - lat0)
//   East_m  = R * (lon - lon0) * cos(lat0)
//   Down_m  = alt0 - alt
//
// with R = 6378137 m (WGS-84 semi-major axis), angles in radians. It ignores
// ellipsoid flattening, meridian convergence and earth curvature. Horizontal
// error grows roughly with distance^2 from the origin: well under 1 m within
// ~2 km, of order metres at 10-20 km (worse at high latitude). It is NOT valid
// beyond ~20 km from the origin; areas are required to be smaller than that.
// The vertical curvature drop (d^2 / 2R, ~31 m at 20 km) is ignored because
// terrain height comes from the elevation service, not from this formula.
//
// TODO(Phase 2): switch to the projected CRS declared in area.yaml
// (`crs.projected`, e.g. EPSG:32644 UTM) once the terrain pipeline provides it
// in-engine (docs/03_DIGITAL_TERRAIN_TWINS.md, docs/10_ROADMAP.md).

#pragma once

#include "CoreMinimal.h"

struct FCDSimGeoOrigin
{
	static constexpr double EarthRadiusM = 6378137.0;

	double LatDeg = 0.0;
	double LonDeg = 0.0;
	double AltMslM = 0.0;

	/** WGS-84 lat/lon (deg) and altitude MSL (m) -> local NED metres about the origin. */
	FVector GeoToNed(double Lat, double Lon, double AltMsl) const
	{
		const double North = EarthRadiusM * FMath::DegreesToRadians(Lat - LatDeg);
		const double East =
			EarthRadiusM * FMath::DegreesToRadians(Lon - LonDeg) * FMath::Cos(FMath::DegreesToRadians(LatDeg));
		const double Down = AltMslM - AltMsl;
		return FVector(North, East, Down);
	}

	/** Local NED metres -> WGS-84 lat/lon (deg) and altitude MSL (m). Inverse of GeoToNed. */
	void NedToGeo(const FVector& Ned, double& OutLat, double& OutLon, double& OutAltMsl) const
	{
		OutLat = LatDeg + FMath::RadiansToDegrees(Ned.X / EarthRadiusM);
		OutLon = LonDeg + FMath::RadiansToDegrees(Ned.Y / (EarthRadiusM * FMath::Cos(FMath::DegreesToRadians(LatDeg))));
		OutAltMsl = AltMslM - Ned.Z;
	}
};
