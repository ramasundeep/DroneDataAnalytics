// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Contract between the CD Sim vehicle (which OWNS physics) and an external
// autopilot running in software-in-the-loop. docs/ADR/0003: ArduPilot SITL is
// unmodified and talks to us through its JSON physics backend; PX4 comes later
// as another implementation of this same interface (e.g. a
// UPX4SimulatorMavlinkBinding speaking HIL_SENSOR / HIL_ACTUATOR_CONTROLS).
// The pawn never knows which autopilot it is talking to.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"

#include "CDSimPhysicsBinding.generated.h"

/** Sensor truth handed to the autopilot each physics step. Aerospace frames, SI. */
struct FCDSimAutopilotSensorState
{
	/** Sim time, seconds (SimTimeUs * 1e-6). The autopilot's clock follows this. */
	double TimestampS = 0.0;
	/** Body FRD angular rate, rad/s. */
	FVector GyroFrdRadps = FVector::ZeroVector;
	/** Body FRD specific force, m/s^2 (at rest: 0, 0, -9.81). */
	FVector AccelFrdMps2 = FVector::ZeroVector;
	/** Local NED position about the area origin, metres. */
	FVector PositionNedM = FVector::ZeroVector;
	/** Roll, pitch, yaw, radians (ZYX aerospace Euler of FRD->NED). */
	FVector AttitudeRpyRad = FVector::ZeroVector;
	/** NED velocity, m/s. */
	FVector VelocityNedMps = FVector::ZeroVector;
};

UINTERFACE(MinimalAPI, meta = (CannotImplementInterfaceInBlueprint))
class UCDSimPhysicsBinding : public UInterface
{
	GENERATED_BODY()
};

/**
 * C++-only interface. Call order, once per 400 Hz physics step on the
 * server / standalone instance:
 *   1. ReceiveActuatorCommands()  — latest autopilot outputs, non-blocking
 *   2. (pawn integrates physics)
 *   3. SendSensorState()          — reply with the new state
 */
class CDSIM_API ICDSimPhysicsBinding
{
	GENERATED_BODY()

public:
	/** Open sockets etc. Returns false (and logs) on failure. */
	virtual bool StartBinding() = 0;

	/** Close everything. Safe to call twice. */
	virtual void StopBinding() = 0;

	/**
	 * Non-blocking. If new commands arrived since the last call, write them
	 * as normalised [0, 1] values indexed by 0-based output channel into
	 * OutNormalised and return true. Otherwise leave OutNormalised untouched
	 * and return false (the pawn holds the last commands).
	 */
	virtual bool ReceiveActuatorCommands(TArray<float>& OutNormalised) = 0;

	/** Send the post-step state to the autopilot. */
	virtual void SendSensorState(const FCDSimAutopilotSensorState& State) = 0;

	/** True once the autopilot has been heard from. */
	virtual bool IsConnected() const = 0;

	/** Human-readable name for logs, e.g. "ArduPilotJSON". */
	virtual FName GetBindingName() const = 0;
};
