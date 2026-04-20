import '../../../../core/auth/firebase_auth_service.dart';
import '../../../../core/network/api_services.dart';
import '../models/register_request.dart';
import '../models/user_response.dart';

class AuthRepository {

  final ApiServices api;
  final FirebaseAuthService firebase;

  AuthRepository(this.api,this.firebase);

  Future<UserResponse> login() async {

    final token = await firebase.getToken();

    return await api.login("Bearer $token");
  }

  Future<UserResponse> register(RegisterRequest body) async {

    final token = await firebase.getToken();

    return await api.register("Bearer $token",body);
  }
}