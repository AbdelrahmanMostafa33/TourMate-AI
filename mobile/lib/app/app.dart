import 'package:flutter/material.dart';
import 'app_router.dart';
import 'app_theme.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TourMate',
      debugShowCheckedModeBanner: false,
      theme: buildTourMateTheme(),
      onGenerateRoute: AppRouter.generateRoute,
      initialRoute: '/',
    );
  }
}