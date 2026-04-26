import 'package:flutter_bloc/flutter_bloc.dart';
import '../data/repository/profile_repository.dart';
import 'profile_state.dart';

class ProfileCubit extends Cubit<ProfileState> {
  final ProfileRepository repo;

  ProfileCubit(this.repo) : super(const ProfileState.initial());

  /// Fetch profile from API
  Future<void> fetchProfile() async {
    emit(const ProfileState.loading());

    final result = await repo.getProfile();

    result.when(
      success: (data) {
        emit(ProfileState.success(data));
      },
      failure: (String message) {
        emit(ProfileState.error(message));
      },
    );
  }


  /// Optional: Refresh (same as fetch but reusable)
  Future<void> refreshProfile() async {
    await fetchProfile();
  }

  /// Optional: Retry after error
  void retry() {
    fetchProfile();
  }
}