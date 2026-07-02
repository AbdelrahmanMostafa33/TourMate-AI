import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme/design_tokens.dart';

// ═══════════════════════════════════════════════════════════════════════════════
// TOURMATE DESIGN SYSTEM — Deep Royal Blue · Midnight Navy · Sapphire
// ═══════════════════════════════════════════════════════════════════════════════
//
// A sophisticated, luxury design language built around:
//   • Deep Royal Blue #1E3A8A — authority, depth, premium feel
//   • Midnight Navy   #0F172A — rich darkness, elegance
//   • Sapphire Blue   #2563EB — refined accent, sparingly used
//
// Usage:  Theme.of(context).extension<TourMateColors>()!
//         context.tm (shortcut)
//
// ═══════════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────────────────────────
// COLOR PALETTE
// ─────────────────────────────────────────────────────────────────────────────

class TourMateColors extends ThemeExtension<TourMateColors> {
  // ――― Core ―――
  final Color deepNavy;
  final Color brandWhite;
  final Color nearWhite;

  // ――― Sapphire Blue accents — refined, elegant, restrained ―――
  final Color sapphire;        // Sapphire Blue accent
  final Color sapphireLight;   // Lighter sapphire
  final Color sapphireDark;    // Deeper sapphire
  final Color sapphireSurface; // Light blue surface
  final Color sapphireBorder;  // Blue-tinted border

  // ――― Surfaces ―――
  final Color surface;
  final Color surfaceElevated;
  final Color surfaceDark;
  final Color border;
  final Color borderLight;
  final Color divider;

  // ――― Text ―――
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textOnDark;
  final Color textOnAccent;

  // ――― Functional ―――
  final Color success;
  final Color error;
  final Color warning;
  final Color info;

  // ――― Navigation ―――
  final Color navActive;
  final Color navInactive;
  final Color navBackground;

  // ――― Premium overlays ―――
  final Color sapphireOverlay;
  final Color blackOverlay;

  // ――― Deep Royal Blue for primary brand moments ―――
  final Color deepRoyalBlue;

  const TourMateColors({
    // Core
    this.deepNavy = const Color(0xFF1E3A8A),      // Deep Royal Blue (formerly deepNavy)
    this.brandWhite = const Color(0xFFFFFFFF),
    this.nearWhite = const Color(0xFFF8FAFC),

    // Sapphire Blue accents — refined, not bright
    this.sapphire = const Color(0xFF2563EB),            // Sapphire Blue
    this.sapphireLight = const Color(0xFF60A5FA),        // Lighter sapphire
    this.sapphireDark = const Color(0xFF1D4ED8),         // Deeper sapphire
    this.sapphireSurface = const Color(0xFFEFF6FF),      // Very light blue
    this.sapphireBorder = const Color(0x4D2563EB),       // Blue border with alpha

    // Surfaces
    this.surface = const Color(0xFFF8FAFC),
    this.surfaceElevated = const Color(0xFFFFFFFF),
    this.surfaceDark = const Color(0xFF0F172A),      // Midnight Navy
    this.border = const Color(0xFFE2E8F0),
    this.borderLight = const Color(0xFFF1F5F9),
    this.divider = const Color(0xFFE2E8F0),

    // Text — rich contrast hierarchy
    this.textPrimary = const Color(0xFF0F172A),       // Midnight Navy
    this.textSecondary = const Color(0xFF64748B),      // Slate Gray
    this.textTertiary = const Color(0xFF94A3B8),       // Light Slate
    this.textOnDark = const Color(0xFFFFFFFF),
    this.textOnAccent = const Color(0xFFFFFFFF),

    // Functional — refined for sophistication
    this.success = const Color(0xFF059669),
    this.error = const Color(0xFFDC2626),
    this.warning = const Color(0xFFD97706),
    this.info = const Color(0xFF2563EB),

    // Navigation
    this.navActive = const Color(0xFF1E3A8A),
    this.navInactive = const Color(0xFF94A3B8),
    this.navBackground = const Color(0xFFFFFFFF),

    // Premium overlays
    this.sapphireOverlay = const Color(0x142563EB),
    this.blackOverlay = const Color(0x0A0F172A),

    // Deep Royal Blue for primary brand moments
    this.deepRoyalBlue = const Color(0xFF1E3A8A),
  });

  @override
  ThemeExtension<TourMateColors> copyWith({
    Color? deepNavy,
    Color? brandWhite,
    Color? nearWhite,
    Color? sapphire,
    Color? sapphireLight,
    Color? sapphireDark,
    Color? sapphireSurface,
    Color? sapphireBorder,
    Color? surface,
    Color? surfaceElevated,
    Color? surfaceDark,
    Color? border,
    Color? borderLight,
    Color? divider,
    Color? textPrimary,
    Color? textSecondary,
    Color? textTertiary,
    Color? textOnDark,
    Color? textOnAccent,
    Color? success,
    Color? error,
    Color? warning,
    Color? info,
    Color? navActive,
    Color? navInactive,
    Color? navBackground,
    Color? sapphireOverlay,
    Color? blackOverlay,
    Color? deepRoyalBlue,
  }) {
    return TourMateColors(
      deepNavy: deepNavy ?? this.deepNavy,
      brandWhite: brandWhite ?? this.brandWhite,
      nearWhite: nearWhite ?? this.nearWhite,
      sapphire: sapphire ?? this.sapphire,
      sapphireLight: sapphireLight ?? this.sapphireLight,
      sapphireDark: sapphireDark ?? this.sapphireDark,
      sapphireSurface: sapphireSurface ?? this.sapphireSurface,
      sapphireBorder: sapphireBorder ?? this.sapphireBorder,
      surface: surface ?? this.surface,
      surfaceElevated: surfaceElevated ?? this.surfaceElevated,
      surfaceDark: surfaceDark ?? this.surfaceDark,
      border: border ?? this.border,
      borderLight: borderLight ?? this.borderLight,
      divider: divider ?? this.divider,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textTertiary: textTertiary ?? this.textTertiary,
      textOnDark: textOnDark ?? this.textOnDark,
      textOnAccent: textOnAccent ?? this.textOnAccent,
      success: success ?? this.success,
      error: error ?? this.error,
      warning: warning ?? this.warning,
      info: info ?? this.info,
      navActive: navActive ?? this.navActive,
      navInactive: navInactive ?? this.navInactive,
      navBackground: navBackground ?? this.navBackground,
      sapphireOverlay: sapphireOverlay ?? this.sapphireOverlay,
      blackOverlay: blackOverlay ?? this.blackOverlay,
      deepRoyalBlue: deepRoyalBlue ?? this.deepRoyalBlue,
    );
  }

  @override
  ThemeExtension<TourMateColors> lerp(
    ThemeExtension<TourMateColors>? other,
    double t,
  ) {
    if (other is! TourMateColors) return this;
    return TourMateColors(
      deepNavy: Color.lerp(deepNavy, other.deepNavy, t)!,
      brandWhite: Color.lerp(brandWhite, other.brandWhite, t)!,
      nearWhite: Color.lerp(nearWhite, other.nearWhite, t)!,
      sapphire: Color.lerp(sapphire, other.sapphire, t)!,
      sapphireLight: Color.lerp(sapphireLight, other.sapphireLight, t)!,
      sapphireDark: Color.lerp(sapphireDark, other.sapphireDark, t)!,
      sapphireSurface: Color.lerp(sapphireSurface, other.sapphireSurface, t)!,
      sapphireBorder: Color.lerp(sapphireBorder, other.sapphireBorder, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceElevated: Color.lerp(surfaceElevated, other.surfaceElevated, t)!,
      surfaceDark: Color.lerp(surfaceDark, other.surfaceDark, t)!,
      border: Color.lerp(border, other.border, t)!,
      borderLight: Color.lerp(borderLight, other.borderLight, t)!,
      divider: Color.lerp(divider, other.divider, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textTertiary: Color.lerp(textTertiary, other.textTertiary, t)!,
      textOnDark: Color.lerp(textOnDark, other.textOnDark, t)!,
      textOnAccent: Color.lerp(textOnAccent, other.textOnAccent, t)!,
      success: Color.lerp(success, other.success, t)!,
      error: Color.lerp(error, other.error, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      info: Color.lerp(info, other.info, t)!,
      navActive: Color.lerp(navActive, other.navActive, t)!,
      navInactive: Color.lerp(navInactive, other.navInactive, t)!,
      navBackground: Color.lerp(navBackground, other.navBackground, t)!,
      sapphireOverlay: Color.lerp(sapphireOverlay, other.sapphireOverlay, t)!,
      blackOverlay: Color.lerp(blackOverlay, other.blackOverlay, t)!,
      deepRoyalBlue: Color.lerp(deepRoyalBlue, other.deepRoyalBlue, t)!,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// TYPOGRAPHY — Inter font family with refined luxury hierarchy
// ─────────────────────────────────────────────────────────────────────────────

class TMTextStyles {
  // Display — for hero moments and splash screens
  static TextStyle displayLarge = GoogleFonts.inter(
    fontSize: 36,
    fontWeight: FontWeight.w700,
    letterSpacing: -1.2,
    height: 1.05,
  );
  static TextStyle displayMedium = GoogleFonts.inter(
    fontSize: 30,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.8,
    height: 1.1,
  );

  // Headings — clear hierarchy
  static TextStyle headlineLarge = GoogleFonts.inter(
    fontSize: 24,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.4,
    height: 1.15,
  );
  static TextStyle headlineMedium = GoogleFonts.inter(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.3,
    height: 1.2,
  );
  static TextStyle headlineSmall = GoogleFonts.inter(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    height: 1.25,
  );

  // Titles
  static TextStyle titleLarge = GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.3,
  );
  static TextStyle titleMedium = GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    height: 1.35,
  );
  static TextStyle titleSmall = GoogleFonts.inter(
    fontSize: 13,
    fontWeight: FontWeight.w600,
    height: 1.4,
  );

  // Body — optimized for readability
  static TextStyle bodyLarge = GoogleFonts.inter(
    fontSize: 15,
    fontWeight: FontWeight.w400,
    height: 1.6,
    letterSpacing: 0.1,
  );
  static TextStyle bodyMedium = GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.55,
    letterSpacing: 0.1,
  );
  static TextStyle bodySmall = GoogleFonts.inter(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.1,
  );

  // Labels — compact, readable
  static TextStyle labelLarge = GoogleFonts.inter(
    fontSize: 13,
    fontWeight: FontWeight.w600,
    height: 1.3,
    letterSpacing: 0.3,
  );
  static TextStyle labelMedium = GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w600,
    height: 1.3,
    letterSpacing: 0.4,
  );
  static TextStyle labelSmall = GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    height: 1.3,
    letterSpacing: 0.5,
  );

  // Utility styles
  static TextStyle caption = GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w500,
    height: 1.3,
    letterSpacing: 0.3,
  );
  static TextStyle captionBold = GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w700,
    height: 1.3,
    letterSpacing: 0.5,
  );
  static TextStyle overline = GoogleFonts.inter(
    fontSize: 10,
    fontWeight: FontWeight.w700,
    height: 1.3,
    letterSpacing: 1.5,
  );

  // Premium price style
  static TextStyle price = GoogleFonts.inter(
    fontSize: 17,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.3,
    height: 1.1,
  );
  static TextStyle priceSmall = GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
    height: 1.1,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CUSTOM WIDGET HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/// Sapphire-tinted divider line for premium section separation.
class BrandDivider extends StatelessWidget {
  final double thickness;
  final double indent;
  final double endIndent;

  const BrandDivider({
    super.key,
    this.thickness = 0.5,
    this.indent = 0,
    this.endIndent = 0,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Container(
      height: thickness,
      margin: EdgeInsets.only(left: indent, right: endIndent),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            tm.sapphire.withValues(alpha: 0.0),
            tm.sapphire.withValues(alpha: 0.4),
            tm.sapphire.withValues(alpha: 0.0),
          ],
        ),
      ),
    );
  }
}

/// A thin sapphire underline accent for active states.
class BrandUnderline extends StatelessWidget {
  final double width;

  const BrandUnderline({super.key, this.width = 24});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Container(
      width: width,
      height: 2,
      decoration: BoxDecoration(
        color: tm.sapphire,
        borderRadius: BorderRadius.circular(1),
      ),
    );
  }
}

/// Premium loading shimmer widget using sapphire tones.
class BrandShimmer extends StatefulWidget {
  final double width;
  final double height;
  final double borderRadius;

  const BrandShimmer({
    super.key,
    this.width = double.infinity,
    this.height = 16,
    this.borderRadius = 4,
  });

  @override
  State<BrandShimmer> createState() => _BrandShimmerState();
}

class _BrandShimmerState extends State<BrandShimmer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            gradient: LinearGradient(
              begin: Alignment(-1.0 + _controller.value * 2, 0),
              end: Alignment(1.0 + _controller.value * 2, 0),
              colors: const [
                Color(0xFFF1F5F9),
                Color(0xFFEFF6FF),
                Color(0xFFDBEAFE),
                Color(0xFFEFF6FF),
                Color(0xFFF1F5F9),
              ],
              stops: const [0.0, 0.3, 0.5, 0.7, 1.0],
            ),
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// BUILD THEME
// ─────────────────────────────────────────────────────────────────────────────

ThemeData buildTourMateTheme() {
  const tm = TourMateColors();

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: ColorScheme.light(
      primary: tm.deepRoyalBlue,
      onPrimary: tm.brandWhite,
      primaryContainer: tm.sapphireSurface,
      onPrimaryContainer: tm.sapphireDark,
      secondary: tm.deepRoyalBlue,
      onSecondary: tm.brandWhite,
      secondaryContainer: tm.sapphireLight,
      onSecondaryContainer: tm.sapphireDark,
      tertiary: tm.surfaceDark,
      onTertiary: tm.brandWhite,
      surface: tm.nearWhite,
      onSurface: tm.textPrimary,
      surfaceContainerHighest: tm.surface,
      onSurfaceVariant: tm.textSecondary,
      outline: tm.border,
      outlineVariant: tm.borderLight,
      error: tm.error,
      onError: tm.brandWhite,
      shadow: tm.deepNavy.withValues(alpha: 0.08),
    ),
    scaffoldBackgroundColor: tm.nearWhite,
    extensions: [tm],

    // ──── Page Transitions ────────────────────────────────
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: CupertinoPageTransitionsBuilder(),
        TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      },
    ),

    // ──── Text Theme ─────────────────────────────────────
    textTheme: TextTheme(
      displayLarge: TMTextStyles.displayLarge,
      displayMedium: TMTextStyles.displayMedium,
      headlineLarge: TMTextStyles.headlineLarge,
      headlineMedium: TMTextStyles.headlineMedium,
      headlineSmall: TMTextStyles.headlineSmall,
      titleLarge: TMTextStyles.titleLarge,
      titleMedium: TMTextStyles.titleMedium,
      titleSmall: TMTextStyles.titleSmall,
      bodyLarge: TMTextStyles.bodyLarge,
      bodyMedium: TMTextStyles.bodyMedium,
      bodySmall: TMTextStyles.bodySmall,
      labelLarge: TMTextStyles.labelLarge,
      labelMedium: TMTextStyles.labelMedium,
      labelSmall: TMTextStyles.labelSmall,
    ),

    // ──── AppBar ─────────────────────────────────────────
    appBarTheme: AppBarTheme(
      backgroundColor: tm.brandWhite,
      foregroundColor: tm.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 0.5,
      surfaceTintColor: Colors.transparent,
      centerTitle: true,
      titleTextStyle: GoogleFonts.inter(
        fontSize: 17,
        fontWeight: FontWeight.w600,
        color: tm.textPrimary,
        letterSpacing: -0.2,
      ),
      iconTheme: IconThemeData(
        color: tm.textPrimary,
        size: 24,
      ),
      actionsIconTheme: IconThemeData(
        color: tm.textPrimary,
        size: 22,
      ),
    ),

    // ──── Bottom Navigation ──────────────────────────────
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor: tm.brandWhite,
      selectedItemColor: tm.deepRoyalBlue,
      unselectedItemColor: tm.navInactive,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
      selectedLabelStyle: TMTextStyles.labelSmall.copyWith(
        letterSpacing: 0.3,
      ),
      unselectedLabelStyle: TMTextStyles.labelSmall.copyWith(
        letterSpacing: 0.3,
      ),
    ),

    // ──── Elevated Button ───────────────────────────────
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: tm.deepNavy,
        foregroundColor: tm.brandWhite,
        elevation: 0,
        padding: Insets.button,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
        ),
        textStyle: GoogleFonts.inter(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.3,
        ),
        shadowColor: Colors.transparent,
      ),
    ),

    // ──── Outlined Button ───────────────────────────────
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: tm.textPrimary,
        side: BorderSide(color: tm.border),
        padding: Insets.button,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
        ),
        textStyle: GoogleFonts.inter(
          fontSize: 15,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),

    // ──── Sapphire-toned Filter Chips ──────────────────
    chipTheme: ChipThemeData(
      backgroundColor: tm.surface,
      selectedColor: tm.deepNavy,
      labelStyle: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: tm.textPrimary,
      ),
      secondaryLabelStyle: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: tm.brandWhite,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.full),
        side: BorderSide(color: tm.border),
      ),
      padding: Insets.chip,
      checkmarkColor: tm.brandWhite,
    ),

    // ──── Input Decoration ──────────────────────────────
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: tm.brandWhite,
      contentPadding: Insets.input,
      isDense: true,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        borderSide: BorderSide(color: tm.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        borderSide: BorderSide(color: tm.borderLight),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        borderSide: BorderSide(color: tm.deepNavy, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        borderSide: BorderSide(color: tm.error),
      ),
      hintStyle: GoogleFonts.inter(
        fontSize: 14,
        color: tm.textTertiary,
        fontWeight: FontWeight.w400,
      ),
      labelStyle: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: tm.textSecondary,
        letterSpacing: 0.3,
      ),
      prefixIconColor: tm.textTertiary,
      suffixIconColor: tm.textTertiary,
    ),

    // ──── Divider ────────────────────────────────────────
    dividerTheme: DividerThemeData(
      color: tm.divider,
      thickness: 1,
      space: 1,
    ),

    // ──── Card Theme ─────────────────────────────────────
    cardTheme: CardThemeData(
      color: tm.brandWhite,
      elevation: 0,
      shadowColor: tm.deepNavy.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        side: BorderSide(color: tm.borderLight),
      ),
      clipBehavior: Clip.antiAlias,
      margin: EdgeInsets.zero,
    ),

    // ──── Dialog ─────────────────────────────────────────
    dialogTheme: DialogThemeData(
      backgroundColor: tm.brandWhite,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl5),
      ),
      titleTextStyle: GoogleFonts.inter(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: tm.textPrimary,
        letterSpacing: -0.2,
      ),
      contentTextStyle: GoogleFonts.inter(
        fontSize: 14,
        color: tm.textSecondary,
        height: 1.4,
      ),
    ),

    // ──── Bottom Sheet ──────────────────────────────────
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: tm.brandWhite,
      elevation: 0,
      showDragHandle: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(RadiusTokens.xl5)),
      ),
      modalBackgroundColor: tm.brandWhite,
      modalElevation: 0,
    ),

    // ──── Snackbar ───────────────────────────────────────
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: tm.deepNavy,
      contentTextStyle: GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: tm.brandWhite,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl2),
      ),
      elevation: 8,
      width: 400,
    ),

    // ──── Progress Indicator ────────────────────────────
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: tm.deepRoyalBlue,
      linearTrackColor: tm.borderLight,
      circularTrackColor: tm.borderLight,
    ),

    // ──── Tab Bar ─────────────────────────────────────────
    tabBarTheme: TabBarThemeData(
      labelColor: tm.brandWhite,
      unselectedLabelColor: tm.textSecondary,
      indicatorSize: TabBarIndicatorSize.tab,
      dividerColor: Colors.transparent,
      labelStyle: TMTextStyles.labelLarge,
      unselectedLabelStyle: TMTextStyles.labelMedium,
      indicator: BoxDecoration(
        color: tm.deepRoyalBlue,
        borderRadius: BorderRadius.circular(RadiusTokens.md),
      ),
    ),

    // ──── Drawer ─────────────────────────────────────────
    drawerTheme: DrawerThemeData(
      backgroundColor: tm.brandWhite,
      elevation: 0,
    ),

    // ──── Popup Menu ─────────────────────────────────────
    popupMenuTheme: PopupMenuThemeData(
      color: tm.brandWhite,
      elevation: 8,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        side: BorderSide(color: tm.borderLight),
      ),
    ),

    // ──── Floating Action Button ─────────────────────────
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: tm.deepNavy,
      foregroundColor: tm.brandWhite,
      elevation: 4,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
      ),
    ),

    // ──── Checkbox / Radio ────────────────────────────────
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return tm.deepNavy;
        return Colors.transparent;
      }),
      checkColor: WidgetStateProperty.all(tm.brandWhite),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xs),
      ),
    ),

    // ──── Scrollbar ──────────────────────────────────────
    scrollbarTheme: ScrollbarThemeData(
      thumbColor: WidgetStateProperty.all(tm.border),
      trackVisibility: WidgetStateProperty.all(false),
      thickness: WidgetStateProperty.all(3),
      radius: const Radius.circular(4),
    ),

    // ──── Dropdown ───────────────────────────────────────
    dropdownMenuTheme: DropdownMenuThemeData(
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: tm.brandWhite,
        contentPadding: Insets.input,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          borderSide: BorderSide(color: tm.border),
        ),
      ),
    ),

    // ──── Time Picker ─────────────────────────────────────
    timePickerTheme: TimePickerThemeData(
      backgroundColor: tm.brandWhite,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
      ),
    ),

    // ──── Banner ──────────────────────────────────────────
    bannerTheme: MaterialBannerThemeData(
      backgroundColor: tm.brandWhite,
      padding: const EdgeInsets.all(Spacing.xl3),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SHORTHAND EXTENSION
// ─────────────────────────────────────────────────────────────────────────────

extension TourMateTheme on BuildContext {
  TourMateColors get tm => Theme.of(this).extension<TourMateColors>()!;
}
