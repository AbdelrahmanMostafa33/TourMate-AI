import 'package:freezed_annotation/freezed_annotation.dart';

import '../../quiz/data/models/persona_response.dart';


part 'profile_state.freezed.dart';

@freezed
class ProfileState with _$ProfileState {
  const factory ProfileState.initial() = _Initial;

  const factory ProfileState.loading() = _Loading;

  const factory ProfileState.success(PersonaResponse data) = _Success;

  const factory ProfileState.error(String message) = _Error;
}