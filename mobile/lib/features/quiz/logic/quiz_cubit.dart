import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/repository/quiz_repository.dart';
import 'quiz_state.dart';

class QuizCubit extends Cubit<QuizState> {
  final QuizRepository repo;

  QuizCubit(this.repo) : super(const QuizState.initial());

  /// Submit quiz answers
  Future<void> submitQuiz(Map<String, dynamic> body) async {
    emit(const QuizState.loading());

    final result = await repo.submitQuiz(body);

    result.when(
      success: (data) => emit(QuizState.success(data)),
      failure: (msg) => emit(QuizState.error(msg)),
    );
  }

  /// Skip quiz
  Future<void> skipQuiz() async {
    emit(const QuizState.loading());

    final result = await repo.skipQuiz();

    result.when(
      success: (_) => emit(const QuizState.skipSuccess()),
      failure: (msg) => emit(QuizState.error(msg)),
    );
  }
}