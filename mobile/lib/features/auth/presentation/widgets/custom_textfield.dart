import 'package:flutter/material.dart';

class CustomTextField extends StatefulWidget {
  final TextEditingController controller;
  final String hint;
  final bool isPassword;

  const CustomTextField({
    super.key,
    required this.controller,
    required this.hint,
    this.isPassword = false,
  });

  @override
  State<CustomTextField> createState() => _CustomTextFieldState();
}

class _CustomTextFieldState extends State<CustomTextField> {

  bool obscure = true;

  @override
  Widget build(BuildContext context) {

    return Container(
      height: 55,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(30),
      ),

      child: TextField(
        controller: widget.controller,
        obscureText: widget.isPassword ? obscure : false,

        decoration: InputDecoration(
          hintText: widget.hint,
          border: InputBorder.none,

        contentPadding: const EdgeInsets.symmetric(
          horizontal: 20,
          vertical: 16,
        ),

        
          suffixIcon: widget.isPassword
              ? IconButton(
            icon: Icon(
              obscure
                  ? Icons.visibility_off
                  : Icons.visibility,
            ),
            onPressed: () {
              setState(() {
                obscure = !obscure;
              });
            },
          )
              : null,
        ),
      ),
    );
  }
}