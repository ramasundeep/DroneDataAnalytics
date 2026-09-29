// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Sensors/CDSimSensorComponent.h"
#include "World/CDSimGeo.h"

#include "CDSimGpsComponent.generated.h"

/**
 * GNSS receiver (platform.yaml `type: gps`). Noise keys: horizontal_m,
 * vertical_m (white Gaussian, 1 sigma). Converts the local NED fix to WGS-84
 * using the area origin (World/CDSimGeo.h flat-earth approximation).
 *
 * TODO(Phase 3): correlated (Gauss-Markov) error, fix-quality / satellite
 * count, and the `gps_loss` failure mode via SetDropout (docs/10_ROADMAP.md).
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimGpsComponent : public UCDSimSensorComponent
{
	GENERATED_BODY()

public:
	virtual void ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed) override;

	/** Set by the pawn from UCDSimAreaLoader after the area is loaded. */
	void SetGeoOrigin(const FCDSimGeoOrigin& InOrigin) { Origin = InOrigin; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	double GetLatitudeDeg() const { return LatDeg; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	double GetLongitudeDeg() const { return LonDeg; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	double GetAltitudeMslM() const { return AltMslM; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	FVector GetVelocityNedMps() const { return VelocityNedMps; }

protected:
	virtual void Sample(int64 SimTimeUs, const FCDSimRigidBodyState& Truth) override;

private:
	FCDSimGeoOrigin Origin;
	double HorizontalSigmaM = 0.0;
	double VerticalSigmaM = 0.0;
	double LatDeg = 0.0;
	double LonDeg = 0.0;
	double AltMslM = 0.0;
	FVector VelocityNedMps = FVector::ZeroVector;
};
