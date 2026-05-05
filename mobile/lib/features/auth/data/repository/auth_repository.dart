import '../datasource/firebase_auth_service.dart';
import '../../../../core/network/api_services.dart';
import '../models/register_request.dart';
import '../models/user_response.dart';

class AuthRepository {

  final ApiServices api;
  final FirebaseAuthService firebase;

  AuthRepository(this.api,this.firebase);

  Future<UserResponse> login() async {

    return await api.login();
  }

  Future<UserResponse> register(RegisterRequest body) async {

    return await api.register(body);
  }
}