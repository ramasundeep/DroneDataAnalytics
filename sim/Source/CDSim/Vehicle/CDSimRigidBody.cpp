// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/CDSimRigidBody.h"

#include "Core/CDSimFrames.h"
#include "Vehicle/CDSimPlatformSpec.h"

// --------------------------------------------------------------------------
// FCDSimRigidBody
// --------------------------------------------------------------------------

void FCDSimRigidBody::Configure(const FCDSimPlatformSpec& Spec)
{
	MassKg = FMath::Max(static_cast<double>(Spec.MassKg), UE_KINDA_SMALL_NUMBER);
	InertiaDiagKgm2 = FVector(FMath::Max(Spec.InertiaKgm2.X, UE_KINDA_SMALL_NUMBER),
		FMath::Max(Spec.InertiaKgm2.Y, UE_KINDA_SMALL_NUMBER), FMath::Max(Spec.InertiaKgm2.Z, UE_KINDA_SMALL_NUMBER));
	LinearDragFrd = Spec.LinearDragFrd;
}

void FCDSimRigidBody::Reset(const FCDSimRigidBodyState& InitialState)
{
	State = InitialState;
	State.AttitudeFrdToNed.Normalize();
	LastImpactSpeedMps = 0.0;
}

void FCDSimRigidBody::Step(const FCDSimForceTorque& Actuation, double DtS)
{
	if (DtS <= 0.0)
	{
		return;
	}
	const FQuat& Q = State.AttitudeFrdToNed;
	const FVector GravityNed(0.0, 0.0, CDSimFrames::GravityMps2);

	// --- Forces (body), then to NED --------------------------------------
	const FVector VelocityFrd = Q.UnrotateVector(State.VelocityNedMps);
	const FVector DragFrd = -LinearDragFrd * VelocityFrd; // linear drag, per axis
	const FVector ForceNed = Q.RotateVector(Actuation.ForceFrdN + DragFrd);

	// --- Translational ---------------------------------------------------
	const FVector PreviousVelocity = State.VelocityNedMps;
	FVector Acceleration = ForceNed / MassKg + GravityNed;
	FVector Velocity = State.VelocityNedMps + Acceleration * DtS;
	FVector Position = State.PositionNedM + Velocity * DtS;

	// --- Rotational: I*wdot = tau - w x (I*w) ----------------------------
	const FVector& W = State.AngularVelocityFrdRadps;
	const FVector IW = InertiaDiagKgm2 * W;
	const FVector AngularAcceleration = (Actuation.TorqueFrdNm - FVector::CrossProduct(W, IW)) / InertiaDiagKgm2;
	FVector Omega = W + AngularAcceleration * DtS;

	// Attitude update with body rates: q <- q * exp(omega * dt / 2).
	FQuat Attitude = Q;
	const double RotationAngle = Omega.Size() * DtS;
	if (RotationAngle > UE_DOUBLE_SMALL_NUMBER)
	{
		const FQuat Delta(Omega.GetSafeNormal(), RotationAngle);
		Attitude = Attitude * Delta;
		Attitude.Normalize();
	}

	// --- Ground contact (flat plane at GroundDownM) ------------------------
	// Crude but deterministic: no penetration, no bounce, full friction.
	// TODO(Phase 2): terrain-height contact; TODO(Phase 3): landing-gear model
	// and hard-landing outcome events (docs/10_ROADMAP.md).
	bool bOnGround = false;
	if (Position.Z >= GroundDownM && Velocity.Z >= 0.0)
	{
		if (!State.bOnGround)
		{
			LastImpactSpeedMps = Velocity.Z;
		}
		Position.Z = GroundDownM;
		Velocity = FVector::ZeroVector;
		Omega = FVector::ZeroVector;
		// Settle level, keeping heading.
		const FVector Rpy = CDSimFrames::QuatToEulerRpyRad(Attitude);
		Attitude = CDSimFrames::EulerRpyRadToQuat(0.0, 0.0, Rpy.Z);
		bOnGround = true;
	}

	// Specific force = actual acceleration minus gravity, in body frame.
	Acceleration = (Velocity - PreviousVelocity) / DtS;
	State.SpecificForceFrdMps2 = Attitude.UnrotateVector(Acceleration - GravityNed);

	State.PositionNedM = Position;
	State.VelocityNedMps = Velocity;
	State.AngularVelocityFrdRadps = Omega;
	State.AttitudeFrdToNed = Attitude;
	State.bOnGround = bOnGround;
}

// --------------------------------------------------------------------------
// FCDSimMultirotorModel
// --------------------------------------------------------------------------

void FCDSimMultirotorModel::Configure(const FCDSimPlatformSpec& Spec)
{
	Rotors.Reset();
	for (const FCDSimActuatorSpec& Actuator : Spec.Actuators)
	{
		FRotor Rotor;
		Rotor.PositionFromCgM = Actuator.PositionM - Spec.CgM;
		Rotor.MaxThrustN = Actuator.MaxThrustN;
		Rotor.MaxTorqueNm = Actuator.MaxTorqueNm;
		Rotor.TimeConstantS = Actuator.TimeConstantS;
		// CCW rotor -> reaction torque on the body is clockwise seen from above = +Z in FRD.
		Rotor.YawSign = Actuator.bCounterClockwise ? 1.0 : -1.0;
		Rotor.ThrustCurve = Actuator.ThrustCurve;
		Rotors.Add(MoveTemp(Rotor));
	}
	MotorOutputs.Init(0.0, Rotors.Num());
}

FCDSimForceTorque FCDSimMultirotorModel::Step(const TArray<float>& Commands, const TArray<float>& Scales, double DtS)
{
	FCDSimForceTorque Out;
	for (int32 Index = 0; Index < Rotors.Num(); ++Index)
	{
		const FRotor& Rotor = Rotors[Index];
		const double Command = Commands.IsValidIndex(Index) ? FMath::Clamp(Commands[Index], 0.0f, 1.0f) : 0.0;
		const double Scale = Scales.IsValidIndex(Index) ? FMath::Clamp(Scales[Index], 0.0f, 1.0f) : 1.0;

		// First-order lag (exact discretisation, deterministic).
		double& Output = MotorOutputs[Index];
		if (Rotor.TimeConstantS > UE_DOUBLE_SMALL_NUMBER)
		{
			const double Alpha = 1.0 - FMath::Exp(-DtS / Rotor.TimeConstantS);
			Output += (Command - Output) * Alpha;
		}
		else
		{
			Output = Command;
		}

		const double ThrustFraction = FCDSimActuatorSpec::EvaluateCurve(Rotor.ThrustCurve, Output) * Scale;
		const FVector ThrustFrd(0.0, 0.0, -Rotor.MaxThrustN * ThrustFraction); // up = -Z in FRD
		Out.ForceFrdN += ThrustFrd;
		Out.TorqueFrdNm += FVector::CrossProduct(Rotor.PositionFromCgM, ThrustFrd);
		Out.TorqueFrdNm.Z += Rotor.YawSign * Rotor.MaxTorqueNm * ThrustFraction;
	}
	return Out;
}
