// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Net/CDSimSessionCode.h"

#include "CDSim.h"
#include "Misc/Guid.h"

const TCHAR* UCDSimSessionCode::GetAlphabet()
{
	// 31 symbols: no 0, O, 1, I, L.
	return TEXT("ABCDEFGHJKMNPQRSTUVWXYZ23456789");
}

FString UCDSimSessionCode::GenerateSessionCode()
{
	const FString Alphabet = GetAlphabet();
	// Seed from a fresh GUID so two servers started in the same second differ.
	// Codes are identifiers, not secrets; FRandomStream is adequate.
	const FGuid Guid = FGuid::NewGuid();
	FRandomStream Stream(static_cast<int32>(GetTypeHash(Guid)));
	FString Code;
	Code.Reserve(CodeLength);
	for (int32 Index = 0; Index < CodeLength; ++Index)
	{
		Code.AppendChar(Alphabet[Stream.RandRange(0, Alphabet.Len() - 1)]);
	}
	return Code;
}

FString UCDSimSessionCode::NormaliseSessionCode(const FString& Code)
{
	FString Out;
	for (const TCHAR Char : Code)
	{
		if (Char == TEXT(' ') || Char == TEXT('-'))
		{
			continue;
		}
		Out.AppendChar(FChar::ToUpper(Char));
	}
	return Out;
}

bool UCDSimSessionCode::IsValidSessionCode(const FString& Code)
{
	const FString Normalised = NormaliseSessionCode(Code);
	if (Normalised.Len() != CodeLength)
	{
		return false;
	}
	const FString Alphabet = GetAlphabet();
	for (const TCHAR Char : Normalised)
	{
		int32 Unused = INDEX_NONE;
		if (!Alphabet.FindChar(Char, Unused))
		{
			return false;
		}
	}
	return true;
}

bool UCDSimSessionCode::ResolveSessionCodeOnLan(const FString& Code, FString& OutServerAddress)
{
	OutServerAddress.Reset();
	UE_LOG(LogCDSim, Warning, TEXT("Session code '%s': LAN discovery not implemented yet (Phase 5, docs/10_ROADMAP.md). "
								   "Join by address instead: open <server-ip>:7777."),
		*NormaliseSessionCode(Code));
	return false;
}
