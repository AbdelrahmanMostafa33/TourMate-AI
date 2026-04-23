import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/persona_response.dart';


part 'quiz_state.freezed.dart';

@freezed
class QuizState with _$QuizState {
  const factory QuizState.initial() = _Initial;

  const factory QuizState.loading() = _Loading;

  const factory QuizState.success(PersonaResponse data) = _Success;

  const factory QuizState.skipSuccess() = _SkipSuccess;

  const factory QuizState.error(String message) = _Error;
}