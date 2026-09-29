// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Coordinate-frame conversion helpers. READ THIS BEFORE TOUCHING ANY MATHS.
//
// CD Sim physics runs in aerospace frames, the same ones ArduPilot and
// platform.yaml use:
//   * World: local NED about the area origin (area.yaml `origin`):
//       x = North, y = East, z = Down, metres. Right-handed.
//   * Body:  FRD: x = Forward, y = Right, z = Down, metres. Right-handed.
//   * Attitude: unit quaternion rotating FRD body vectors into NED.
//
// Unreal Engine uses centimetres and a LEFT-handed frame: X forward, Y right,
// Z up. We fix the UE world so that UE +X = North and UE +Y = East, and the UE
// world origin is the area origin. Then:
//
//   UE_cm = 100 * ( N, E, -D )          (world positions / velocities)
//   UE_body = ( F, R, -D_body )         (body-frame vectors, e.g. sensor mounts)
//
// Mapping (x, y, z) -> (x, y, -z) is a reflection S = diag(1, 1, -1). A
// rotation R in NED becomes S R S in UE. For a quaternion (w, x, y, z) that is
// (w, -x, -y, z). Worked check: a +yaw (clockwise seen from above, North
// towards East) is a rotation about NED +Z; in UE it stays a rotation about
// +Z with the same sign, which UE's FRotator also calls +Yaw. Roll and pitch
// keep their aerospace meaning in FRotator too, so
//   FRotator(PitchDeg, YawDeg, RollDeg) == NedQuatToUe(q_frd_to_ned).Rotator()
// for the aerospace Euler angles (ZYX order) of q.

#pragma once

#include "CoreMinimal.h"

namespace CDSimFrames
{
	/** Metres -> centimetres. */
	inline constexpr double MetresToCm = 100.0;
	/** Standard gravity, m/s^2 (matches ArduPilot SITL). */
	inline constexpr double GravityMps2 = 9.80665;

	/** Local NED metres -> UE world centimetres. */
	FORCEINLINE FVector NedToUeCm(const FVector& Ned)
	{
		return FVector(Ned.X, Ned.Y, -Ned.Z) * MetresToCm;
	}

	/** UE world centimetres -> local NED metres. */
	FORCEINLINE FVector UeCmToNed(const FVector& UeCm)
	{
		return FVector(UeCm.X, UeCm.Y, -UeCm.Z) / MetresToCm;
	}

	/** FRD body metres (e.g. platform.yaml position_m) -> UE body-relative centimetres. */
	FORCEINLINE FVector FrdToUeBodyCm(const FVector& Frd)
	{
		return FVector(Frd.X, Frd.Y, -Frd.Z) * MetresToCm;
	}

	/** Attitude quaternion FRD->NED  ->  UE actor rotation. See header comment. */
	FORCEINLINE FQuat NedQuatToUe(const FQuat& FrdToNed)
	{
		return FQuat(-FrdToNed.X, -FrdToNed.Y, FrdToNed.Z, FrdToNed.W);
	}

	/** UE actor rotation -> attitude quaternion FRD->NED. Inverse of NedQuatToUe. */
	FORCEINLINE FQuat UeQuatToNed(const FQuat& Ue)
	{
		return FQuat(-Ue.X, -Ue.Y, Ue.Z, Ue.W);
	}

	/** platform.yaml mount rotation_deg [roll, pitch, yaw] (FRD) -> UE relative rotator. */
	FORCEINLINE FRotator FrdMountRpyDegToUe(const FVector& RollPitchYawDeg)
	{
		return FRotator(RollPitchYawDeg.Y, RollPitchYawDeg.Z, RollPitchYawDeg.X);
	}

	/**
	 * Aerospace Euler angles (roll, pitch, yaw) in radians, ZYX order, of an
	 * FRD->NED quaternion. This is what ArduPilot's JSON "attitude" expects.
	 */
	FORCEINLINE FVector QuatToEulerRpyRad(const FQuat& Q)
	{
		const double SinRollCosPitch = 2.0 * (Q.W * Q.X + Q.Y * Q.Z);
		const double CosRollCosPitch = 1.0 - 2.0 * (Q.X * Q.X + Q.Y * Q.Y);
		const double Roll = FMath::Atan2(SinRollCosPitch, CosRollCosPitch);

		const double SinPitch = FMath::Clamp(2.0 * (Q.W * Q.Y - Q.Z * Q.X), -1.0, 1.0);
		const double Pitch = FMath::Asin(SinPitch);

		const double SinYawCosPitch = 2.0 * (Q.W * Q.Z + Q.X * Q.Y);
		const double CosYawCosPitch = 1.0 - 2.0 * (Q.Y * Q.Y + Q.Z * Q.Z);
		const double Yaw = FMath::Atan2(SinYawCosPitch, CosYawCosPitch);

		return FVector(Roll, Pitch, Yaw);
	}

	/** Inverse of QuatToEulerRpyRad: FRD->NED quaternion from roll/pitch/yaw radians. */
	FORCEINLINE FQuat EulerRpyRadToQuat(double Roll, double Pitch, double Yaw)
	{
		const double Cr = FMath::Cos(Roll * 0.5), Sr = FMath::Sin(Roll * 0.5);
		const double Cp = FMath::Cos(Pitch * 0.5), Sp = FMath::Sin(Pitch * 0.5);
		const double Cy = FMath::Cos(Yaw * 0.5), Sy = FMath::Sin(Yaw * 0.5);
		return FQuat(
			Sr * Cp * Cy - Cr * Sp * Sy, // X
			Cr * Sp * Cy + Sr * Cp * Sy, // Y
			Cr * Cp * Sy - Sr * Sp * Cy, // Z
			Cr * Cp * Cy + Sr * Sp * Sy  // W
		);
	}
} // namespace CDSimFrames
