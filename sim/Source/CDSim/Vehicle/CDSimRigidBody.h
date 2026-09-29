// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Deterministic 6-DOF rigid-body + multirotor actuator model, in plain C++.
//
// WHY NOT CHAOS: CD Sim needs bit-for-bit repeatable trajectories for
// deterministic replay (Phase 1 acceptance), golden-session scoring (Phase 3)
// and lock-step RL (Phase 7). Chaos runs on UE's variable frame time /
// async physics thread, may substep differently frame to frame, and is not
// guaranteed deterministic across runs or machines. Here, every step is a
// fixed 2500 us (driven by UCDSimClockSubsystem), uses only double arithmetic
// in a fixed order, and depends on nothing but (state, commands, spec). Given
// the same inputs it produces the same outputs. Chaos is still used for
// visuals-only things (debris, cloth) and scene queries.
//
// All quantities are SI in aerospace frames (NED world, FRD body); see
// Core/CDSimFrames.h. Integration is semi-implicit Euler, adequate at 400 Hz
// for multirotor dynamics.

#pragma once

#include "CoreMinimal.h"

struct FCDSimPlatformSpec;

/** Full kinematic state, NED / FRD, SI units. */
struct CDSIM_API FCDSimRigidBodyState
{
	FVector PositionNedM = FVector::ZeroVector;
	FVector VelocityNedMps = FVector::ZeroVector;
	/** Rotates FRD body vectors into NED. */
	FQuat AttitudeFrdToNed = FQuat::Identity;
	FVector AngularVelocityFrdRadps = FVector::ZeroVector;
	/** Specific force (what an ideal accelerometer reads), body FRD. At rest: (0, 0, -g). */
	FVector SpecificForceFrdMps2 = FVector(0.0, 0.0, -9.80665);
	bool bOnGround = true;
};

/** Force and torque about the CG, body FRD. */
struct FCDSimForceTorque
{
	FVector ForceFrdN = FVector::ZeroVector;
	FVector TorqueFrdNm = FVector::ZeroVector;
};

/** Rigid body integrator. No UObject, no engine state: unit-testable. */
class CDSIM_API FCDSimRigidBody
{
public:
	/** Configure mass, inertia and drag from a platform spec. */
	void Configure(const FCDSimPlatformSpec& Spec);

	void Reset(const FCDSimRigidBodyState& InitialState);

	/** Ground surface NED down coordinate (flat areas). Updated by the pawn from the area loader. */
	void SetGroundDownM(double InGroundDownM) { GroundDownM = InGroundDownM; }

	/** Advance by DtS seconds with the given actuator force/torque (drag and gravity are added here). */
	void Step(const FCDSimForceTorque& Actuation, double DtS);

	const FCDSimRigidBodyState& GetState() const { return State; }

	/** Speed along NED down at the last ground contact, m/s (for touchdown outcome events). */
	double GetLastImpactSpeedMps() const { return LastImpactSpeedMps; }

private:
	FCDSimRigidBodyState State;
	double MassKg = 1.0;
	FVector InertiaDiagKgm2 = FVector::OneVector;
	FVector LinearDragFrd = FVector::ZeroVector;
	double GroundDownM = 0.0;
	double LastImpactSpeedMps = 0.0;
};

/**
 * Multirotor propulsion: first-order motor lag, thrust curve, reaction torque.
 * Motors thrust along body -Z (up). Counter-clockwise rotors (seen from above)
 * push the body with a +Z (yaw-right, FRD) reaction torque and vice versa —
 * this matches ArduPilot's motor-direction convention for quad-X.
 */
class CDSIM_API FCDSimMultirotorModel
{
public:
	void Configure(const FCDSimPlatformSpec& Spec);

	/**
	 * Commands are normalised [0, 1] indexed by actuator (spec order).
	 * Scales are per-actuator multipliers in [0, 1] (failure modes).
	 */
	FCDSimForceTorque Step(const TArray<float>& Commands, const TArray<float>& Scales, double DtS);

	/** Current (lagged) normalised motor outputs, spec order. */
	const TArray<double>& GetMotorOutputs() const { return MotorOutputs; }

private:
	struct FRotor
	{
		FVector PositionFromCgM = FVector::ZeroVector;
		double MaxThrustN = 0.0;
		double MaxTorqueNm = 0.0;
		double TimeConstantS = 0.0;
		double YawSign = 1.0;
		TArray<FVector2D> ThrustCurve;
	};

	TArray<FRotor> Rotors;
	TArray<double> MotorOutputs;
};
