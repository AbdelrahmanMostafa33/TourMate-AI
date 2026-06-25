import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

class ImagePickerService {
  final ImagePicker _picker = ImagePicker();

  /// Pick an image from the gallery
  Future<Uint8List?> pickImageFromGallery() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 85,
        maxWidth: 1920,
        maxHeight: 1920,
      );
      if (image == null) return null;
      return await image.readAsBytes();
    } catch (e) {
      debugPrint('[ImagePickerService] Error picking from gallery: $e');
      return null;
    }
  }

  /// Pick an image from the camera
  Future<Uint8List?> pickImageFromCamera() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
        maxWidth: 1920,
        maxHeight: 1920,
      );
      if (image == null) return null;
      return await image.readAsBytes();
    } catch (e) {
      debugPrint('[ImagePickerService] Error picking from camera: $e');
      return null;
    }
  }

  /// Convert image bytes to base64 string for transmission
  String bytesToBase64(Uint8List bytes) {
    return 'data:image/jpeg;base64,${base64Encode(bytes)}';
  }
}
