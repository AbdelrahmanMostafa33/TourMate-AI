import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme/design_tokens.dart';

// ═══════════════════════════════════════════════════════════════════════════════
// TOURMATE DESIGN SYSTEM — Black · White · Gold
// ═══════════════════════════════════════════════════════════════════════════════
//
// A sophisticated, luxury design language built around:
//   • Deep matte black    — authority, depth, premium feel
//   • Pure white          — clarity, minimalism, space
//   • Warm metallic gold  — prestige, warmth, distinction
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
  final Color pureBlack;
  final Color pureWhite;
  final Color nearWhite;

  // ――― Gold accents — elegant, warm, not too yellow ―――
  final Color gold;
  final Color goldLight;
  final Color goldDark;
  final Color goldSurface;
  final Color goldBorder;

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
  final Color textOnGold;

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
  final Color goldOverlay;
  final Color blackOverlay;

  const TourMateColors({
    // Core
    this.pureBlack = const Color(0xFF0A0A0A),
    this.pureWhite = const Color(0xFFFFFFFF),
    this.nearWhite = const Color(0xFFF7F7F5),

    // Gold accents — refined, warm metallic
    this.gold = const Color(0xFFC8A84E),
    this.goldLight = const Color(0xFFE8D5A3),
    this.goldDark = const Color(0xFF9E8236),
    this.goldSurface = const Color(0xFFFFF9EC),
    this.goldBorder = const Color(0x4DD4AF37),

    // Surfaces
    this.surface = const Color(0xFFF5F5F3),
    this.surfaceElevated = const Color(0xFFFFFFFF),
    this.surfaceDark = const Color(0xFF141414),
    this.border = const Color(0xFFE5E5E0),
    this.borderLight = const Color(0xFFF0F0ED),
    this.divider = const Color(0xFFEEEEEA),

    // Text — rich contrast hierarchy
    this.textPrimary = const Color(0xFF0A0A0A),
    this.textSecondary = const Color(0xFF6B6B6B),
    this.textTertiary = const Color(0xFF9E9E9E),
    this.textOnDark = const Color(0xFFFFFFFF),
    this.textOnGold = const Color(0xFF0A0A0A),

    // Functional — muted for sophistication
    this.success = const Color(0xFF2E7D32),
    this.error = const Color(0xFFC62828),
    this.warning = const Color(0xFFE65100),
    this.info = const Color(0xFF1565C0),

    // Navigation
    this.navActive = const Color(0xFFC8A84E),
    this.navInactive = const Color(0xFF9E9E9E),
    this.navBackground = const Color(0xFFFFFFFF),

    // Premium overlays
    this.goldOverlay = const Color(0x14C8A84E),
    this.blackOverlay = const Color(0x0A0A0A0A),
  });

  @override
  ThemeExtension<TourMateColors> copyWith({
    Color? pureBlack,
    Color? pureWhite,
    Color? nearWhite,
    Color? gold,
    Color? goldLight,
    Color? goldDark,
    Color? goldSurface,
    Color? goldBorder,
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
    Color? textOnGold,
    Color? success,
    Color? error,
    Color? warning,
    Color? info,
    Color? navActive,
    Color? navInactive,
    Color? navBackground,
    Color? goldOverlay,
    Color? blackOverlay,
  }) {
    return TourMateColors(
      pureBlack: pureBlack ?? this.pureBlack,
      pureWhite: pureWhite ?? this.pureWhite,
      nearWhite: nearWhite ?? this.nearWhite,
      gold: gold ?? this.gold,
      goldLight: goldLight ?? this.goldLight,
      goldDark: goldDark ?? this.goldDark,
      goldSurface: goldSurface ?? this.goldSurface,
      goldBorder: goldBorder ?? this.goldBorder,
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
      textOnGold: textOnGold ?? this.textOnGold,
      success: success ?? this.success,
      error: error ?? this.error,
      warning: warning ?? this.warning,
      info: info ?? this.info,
      navActive: navActive ?? this.navActive,
      navInactive: navInactive ?? this.navInactive,
      navBackground: navBackground ?? this.navBackground,
      goldOverlay: goldOverlay ?? this.goldOverlay,
      blackOverlay: blackOverlay ?? this.blackOverlay,
    );
  }

  @override
  ThemeExtension<TourMateColors> lerp(
    ThemeExtension<TourMateColors>? other,
    double t,
  ) {
    if (other is! TourMateColors) return this;
    return TourMateColors(
      pureBlack: Color.lerp(pureBlack, other.pureBlack, t)!,
      pureWhite: Color.lerp(pureWhite, other.pureWhite, t)!,
      nearWhite: Color.lerp(nearWhite, other.nearWhite, t)!,
      gold: Color.lerp(gold, other.gold, t)!,
      goldLight: Color.lerp(goldLight, other.goldLight, t)!,
      goldDark: Color.lerp(goldDark, other.goldDark, t)!,
      goldSurface: Color.lerp(goldSurface, other.goldSurface, t)!,
      goldBorder: Color.lerp(goldBorder, other.goldBorder, t)!,
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
      textOnGold: Color.lerp(textOnGold, other.textOnGold, t)!,
      success: Color.lerp(success, other.success, t)!,
      error: Color.lerp(error, other.error, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      info: Color.lerp(info, other.info, t)!,
      navActive: Color.lerp(navActive, other.navActive, t)!,
      navInactive: Color.lerp(navInactive, other.navInactive, t)!,
      navBackground: Color.lerp(navBackground, other.navBackground, t)!,
      goldOverlay: Color.lerp(goldOverlay, other.goldOverlay, t)!,
      blackOverlay: Color.lerp(blackOverlay, other.blackOverlay, t)!,
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

/// Gold-tinted divider line for premium section separation.
class GoldDivider extends StatelessWidget {
  final double thickness;
  final double indent;
  final double endIndent;

  const GoldDivider({
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
            tm.gold.withValues(alpha: 0.0),
            tm.gold.withValues(alpha: 0.5),
            tm.gold.withValues(alpha: 0.0),
          ],
        ),
      ),
    );
  }
}

/// A thin gold underline accent for active states.
class GoldUnderline extends StatelessWidget {
  final double width;

  const GoldUnderline({super.key, this.width = 24});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Container(
      width: width,
      height: 2,
      decoration: BoxDecoration(
        color: tm.gold,
        borderRadius: BorderRadius.circular(1),
      ),
    );
  }
}

/// Premium loading shimmer widget using gold tones.
class GoldShimmer extends StatefulWidget {
  final double width;
  final double height;
  final double borderRadius;

  const GoldShimmer({
    super.key,
    this.width = double.infinity,
    this.height = 16,
    this.borderRadius = 4,
  });

  @override
  State<GoldShimmer> createState() => _GoldShimmerState();
}

class _GoldShimmerState extends State<GoldShimmer>
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
                Color(0xFFF0F0ED),
                Color(0xFFFFF9EC),
                Color(0xFFF5ECCE),
                Color(0xFFFFF9EC),
                Color(0xFFF0F0ED),
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
      primary: tm.pureBlack,
      onPrimary: tm.pureWhite,
      primaryContainer: tm.goldSurface,
      onPrimaryContainer: tm.goldDark,
      secondary: tm.gold,
      onSecondary: tm.pureBlack,
      secondaryContainer: tm.goldLight,
      onSecondaryContainer: tm.goldDark,
      tertiary: tm.surfaceDark,
      onTertiary: tm.pureWhite,
      surface: tm.nearWhite,
      onSurface: tm.textPrimary,
      surfaceContainerHighest: tm.surface,
      onSurfaceVariant: tm.textSecondary,
      outline: tm.border,
      outlineVariant: tm.borderLight,
      error: tm.error,
      onError: tm.pureWhite,
      shadow: tm.pureBlack.withValues(alpha: 0.08),
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
      backgroundColor: tm.pureWhite,
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
      backgroundColor: tm.pureWhite,
      selectedItemColor: tm.gold,
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
        backgroundColor: tm.pureBlack,
        foregroundColor: tm.pureWhite,
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

    // ──── Gold-toned Filter Chips ──────────────────────
    chipTheme: ChipThemeData(
      backgroundColor: tm.surface,
      selectedColor: tm.pureBlack,
      labelStyle: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: tm.textPrimary,
      ),
      secondaryLabelStyle: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: tm.pureWhite,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.full),
        side: BorderSide(color: tm.border),
      ),
      padding: Insets.chip,
      checkmarkColor: tm.pureWhite,
    ),

    // ──── Input Decoration ──────────────────────────────
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: tm.pureWhite,
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
        borderSide: BorderSide(color: tm.pureBlack, width: 1.5),
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
      color: tm.pureWhite,
      elevation: 0,
      shadowColor: tm.pureBlack.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        side: BorderSide(color: tm.borderLight),
      ),
      clipBehavior: Clip.antiAlias,
      margin: EdgeInsets.zero,
    ),

    // ──── Dialog ─────────────────────────────────────────
    dialogTheme: DialogThemeData(
      backgroundColor: tm.pureWhite,
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
      backgroundColor: tm.pureWhite,
      elevation: 0,
      showDragHandle: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(RadiusTokens.xl5)),
      ),
      modalBackgroundColor: tm.pureWhite,
      modalElevation: 0,
    ),

    // ──── Snackbar ───────────────────────────────────────
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: tm.pureBlack,
      contentTextStyle: GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: tm.pureWhite,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl2),
      ),
      elevation: 8,
      width: 400,
    ),

    // ──── Progress Indicator ────────────────────────────
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: tm.gold,
      linearTrackColor: tm.borderLight,
      circularTrackColor: tm.borderLight,
    ),

    // ──── Tab Bar ─────────────────────────────────────────
    tabBarTheme: TabBarThemeData(
      labelColor: tm.pureWhite,
      unselectedLabelColor: tm.textSecondary,
      indicatorSize: TabBarIndicatorSize.tab,
      dividerColor: Colors.transparent,
      labelStyle: TMTextStyles.labelLarge,
      unselectedLabelStyle: TMTextStyles.labelMedium,
      indicator: BoxDecoration(
        color: tm.pureBlack,
        borderRadius: BorderRadius.circular(RadiusTokens.md),
      ),
    ),

    // ──── Drawer ─────────────────────────────────────────
    drawerTheme: DrawerThemeData(
      backgroundColor: tm.pureWhite,
      elevation: 0,
    ),

    // ──── Popup Menu ─────────────────────────────────────
    popupMenuTheme: PopupMenuThemeData(
      color: tm.pureWhite,
      elevation: 8,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl),
        side: BorderSide(color: tm.borderLight),
      ),
    ),

    // ──── Floating Action Button ─────────────────────────
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: tm.pureBlack,
      foregroundColor: tm.pureWhite,
      elevation: 4,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
      ),
    ),

    // ──── Checkbox / Radio ────────────────────────────────
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return tm.pureBlack;
        return Colors.transparent;
      }),
      checkColor: WidgetStateProperty.all(tm.pureWhite),
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
        fillColor: tm.pureWhite,
        contentPadding: Insets.input,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          borderSide: BorderSide(color: tm.border),
        ),
      ),
    ),

    // ──── Time Picker ─────────────────────────────────────
    timePickerTheme: TimePickerThemeData(
      backgroundColor: tm.pureWhite,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
      ),
    ),

    // ──── Banner ──────────────────────────────────────────
    bannerTheme: MaterialBannerThemeData(
      backgroundColor: tm.pureWhite,
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
