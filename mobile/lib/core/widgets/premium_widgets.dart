import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../app/app_theme.dart';
import '../theme/design_tokens.dart';

// ═══════════════════════════════════════════════════════════════════════════════
// TOURMATE PREMIUM COMPONENT LIBRARY
// ═══════════════════════════════════════════════════════════════════════════════
//
// Every component in this file is custom-crafted for the TourMate
// luxury design language. Nothing is a default Material widget.
//
// ═══════════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM BUTTONS
// ─────────────────────────────────────────────────────────────────────────────

/// Primary black button with sapphire shimmer loading state.
class TMPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;
  final double? width;
  final double height;

  const TMPrimaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.icon,
    this.width,
    this.height = 54,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return SizedBox(
      width: width ?? double.infinity,
      height: height,
      child: ElevatedButton(
        onPressed: isLoading ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: tm.deepNavy,
          foregroundColor: tm.brandWhite,
          disabledBackgroundColor: tm.textTertiary.withValues(alpha: 0.3),
          disabledForegroundColor: tm.textOnDark.withValues(alpha: 0.5),
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(RadiusTokens.xl2),
          ),
          shadowColor: Colors.transparent,
        ),
        child: isLoading
            ? SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  valueColor: AlwaysStoppedAnimation<Color>(tm.brandWhite),
                ),
              )
            : Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: 18),
                    const SizedBox(width: 10),
                  ],
                  Text(
                    label,
                    style: GoogleFonts.inter(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

/// Sapphire accent premium button — for VIP actions.
class TMAccentButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;
  final double? width;

  const TMAccentButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.icon,
    this.width,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return SizedBox(
      width: width ?? double.infinity,
      height: 54,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF3B82F6), Color(0xFF2563EB), Color(0xFF1D4ED8)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
          boxShadow: [
            BoxShadow(
              color: tm.sapphire.withValues(alpha: 0.3),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: ElevatedButton(
          onPressed: isLoading ? null : onPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.transparent,
            foregroundColor: tm.brandWhite,
            disabledBackgroundColor: Colors.transparent,
            disabledForegroundColor: tm.brandWhite.withValues(alpha: 0.5),
            elevation: 0,
            shadowColor: Colors.transparent,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(RadiusTokens.xl2),
            ),
          ),
          child: isLoading
              ? SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    valueColor: AlwaysStoppedAnimation<Color>(tm.brandWhite),
                  ),
                )
              : Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[
                      Icon(icon, size: 18),
                      const SizedBox(width: 10),
                    ],
                    Text(
                      label,
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

/// Outlined sapphire button for secondary premium actions.
class TMOutlinedSapphireButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final double? width;

  const TMOutlinedSapphireButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.width,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return SizedBox(
      width: width ?? double.infinity,
      height: 50,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          foregroundColor: tm.sapphire,
          side: BorderSide(color: tm.sapphire.withValues(alpha: 0.5)),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(RadiusTokens.xl2),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 18),
              const SizedBox(width: 8),
            ],
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Ghost/text button with subtle styling.
class TMTextButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Color? color;

  const TMTextButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return TextButton(
      onPressed: onPressed,
      style: TextButton.styleFrom(
        foregroundColor: color ?? tm.textSecondary,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.md),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 16),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM CARDS
// ─────────────────────────────────────────────────────────────────────────────

/// A premium card container with accent border option.
class TMPremiumCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final bool accentBorder;
  final VoidCallback? onTap;
  final double borderRadius;

  const TMPremiumCard({
    super.key,
    required this.child,
    this.padding,
    this.margin,
    this.accentBorder = false,
    this.onTap,
    this.borderRadius = RadiusTokens.xl3,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final card = Container(
      padding: padding ?? const EdgeInsets.all(Spacing.xl3),
      margin: margin ?? EdgeInsets.zero,
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(
          color: accentBorder ? tm.sapphire.withValues(alpha: 0.4) : tm.borderLight,
          width: accentBorder ? 1.0 : 0.5,
        ),
        boxShadow: [
          ...ShadowTokens.medium(tm.deepNavy),
          if (accentBorder)
            BoxShadow(
              color: tm.sapphire.withValues(alpha: 0.06),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
        ],
      ),
      child: child,
    );

    if (onTap != null) {
      return Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(borderRadius),
        child: InkWell(
          borderRadius: BorderRadius.circular(borderRadius),
          onTap: onTap,
          child: card,
        ),
      );
    }

    return card;
  }
}

/// A premium card with a header icon, title, and subtitle.
class TMPremiumHeaderCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool accentMode;

  const TMPremiumHeaderCard({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
    this.accentMode = false,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return TMPremiumCard(
      accentBorder: accentMode,
      onTap: onTap,
      padding: const EdgeInsets.all(Spacing.xl3),
      child: Row(
        children: [
          // Icon container
          Container(
            padding: const EdgeInsets.all(Spacing.md),
            decoration: BoxDecoration(
              color: accentMode ? tm.sapphireSurface : tm.surface,
              borderRadius: BorderRadius.circular(RadiusTokens.xl),
              border: accentMode
                  ? Border.all(color: tm.sapphire.withValues(alpha: 0.3))
                  : null,
            ),
            child: Icon(
              icon,
              size: IconSizes.lg,
              color: accentMode ? tm.sapphire : tm.textSecondary,
            ),
          ),
          const SizedBox(width: Spacing.xl3),
          // Title + subtitle
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TMTextStyles.titleMedium.copyWith(
                    color: tm.textPrimary,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    subtitle!,
                    style: TMTextStyles.bodySmall.copyWith(
                      color: tm.textTertiary,
                    ),
                  ),
                ],
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM BADGES & CHIPS
// ─────────────────────────────────────────────────────────────────────────────

/// A sapphire-accented premium badge for VIP/pricing/category labels.
class TMBadge extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool isAccented;
  final Color? backgroundColor;
  final Color? textColor;
  final double fontSize;

  const TMBadge({
    super.key,
    required this.label,
    this.icon,
    this.isAccented = false,
    this.backgroundColor,
    this.textColor,
    this.fontSize = 11,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final bg = backgroundColor ?? (isAccented ? tm.sapphireSurface : tm.surface);
    final fg = textColor ?? (isAccented ? tm.sapphireDark : tm.textSecondary);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(RadiusTokens.full),
        border: isAccented
            ? Border.all(color: tm.sapphire.withValues(alpha: 0.3))
            : Border.all(color: tm.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: fontSize,
              fontWeight: FontWeight.w600,
              color: fg,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}

/// Premium rating badge — sapphire star + score.
class TMRatingBadge extends StatelessWidget {
  final double rating;
  final int? reviewCount;
  final double size;

  const TMRatingBadge({
    super.key,
    required this.rating,
    this.reviewCount,
    this.size = 14,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: tm.sapphireSurface,
        borderRadius: BorderRadius.circular(RadiusTokens.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star_rounded, size: size, color: tm.sapphire),
          const SizedBox(width: 3),
          Text(
            rating.toStringAsFixed(1),
            style: GoogleFonts.inter(
              fontSize: size * 0.9,
              fontWeight: FontWeight.w700,
              color: tm.sapphireDark,
            ),
          ),
          if (reviewCount != null && reviewCount! > 0) ...[
            const SizedBox(width: 3),
            Text(
              '(${_formatCount(reviewCount!)})',
              style: GoogleFonts.inter(
                fontSize: size * 0.75,
                color: tm.sapphire.withValues(alpha: 0.7),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _formatCount(int count) {
    if (count >= 1000) return '${(count / 1000).toStringAsFixed(1)}k';
    return count.toString();
  }
}

/// A premium sapphire-accented status chip.
class TMStatusBadge extends StatelessWidget {
  final String label;
  final Color? color;
  final IconData? icon;

  const TMStatusBadge({
    super.key,
    required this.label,
    this.color,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final fg = color ?? tm.sapphireDark;
    final bg = (color ?? tm.sapphire).withValues(alpha: 0.1);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(RadiusTokens.full),
        border: Border.all(color: fg.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: fg,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM SECTION HEADERS
// ─────────────────────────────────────────────────────────────────────────────

/// Section header with optional action button.
class TMSectionHeader extends StatelessWidget {
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool accentMode;

  const TMSectionHeader({
    super.key,
    required this.title,
    this.actionLabel,
    this.onAction,
    this.accentMode = false,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (accentMode) ...[
            const BrandDivider(indent: 0, endIndent: 0, thickness: 0.5),
            const SizedBox(height: Spacing.xl3),
          ],
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.3,
                  ),
                ),
              ),
              if (actionLabel != null && onAction != null)
                TMTextButton(
                  label: actionLabel!,
                  onPressed: onAction,
                  icon: Icons.chevron_right,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Overline-style section label (uppercase, small, spaced).
class TMSectionLabel extends StatelessWidget {
  final String label;
  final Color? color;

  const TMSectionLabel({
    super.key,
    required this.label,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Text(
      label.toUpperCase(),
      style: GoogleFonts.inter(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.2,
        color: color ?? tm.textTertiary,
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM PRICE DISPLAY
// ─────────────────────────────────────────────────────────────────────────────

/// Premium price display with sapphire accent for emphasis.
class TMPriceDisplay extends StatelessWidget {
  final double amount;
  final String currency;
  final bool large;
  final bool useAccentColor;

  const TMPriceDisplay({
    super.key,
    required this.amount,
    this.currency = 'USD',
    this.large = false,
    this.useAccentColor = true,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final symbol = currency == 'USD'
        ? '\$'
        : currency == 'EUR'
            ? '€'
            : '$currency ';
    final formatted = amount == amount.roundToDouble()
        ? '$symbol${amount.toInt()}'
        : '$symbol${amount.toStringAsFixed(2)}';

    return Text(
      formatted,
      style: GoogleFonts.inter(
        fontSize: large ? 22 : 16,
        fontWeight: FontWeight.w700,
        color: useAccentColor ? tm.sapphire : tm.textPrimary,
        letterSpacing: large ? -0.5 : -0.2,
      ),
    );
  }
}

/// Price per unit (e.g., "/night") with premium styling.
class TMPricePerUnit extends StatelessWidget {
  final double amount;
  final String unit;
  final String currency;

  const TMPricePerUnit({
    super.key,
    required this.amount,
    required this.unit,
    this.currency = 'USD',
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final symbol = currency == 'USD' ? '\$' : '$currency ';
    final formatted = amount == amount.roundToDouble()
        ? '$symbol${amount.toInt()}'
        : '$symbol${amount.toStringAsFixed(2)}';

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          formatted,
          style: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: tm.sapphireDark,
          ),
        ),
        const SizedBox(width: 2),
        Text(
          '/ $unit',
          style: GoogleFonts.inter(
            fontSize: 11,
            color: tm.textTertiary,
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM LOADING / EMPTY / ERROR STATES
// ─────────────────────────────────────────────────────────────────────────────

/// Elegant loading placeholder with the TM blue spinner.
class TMLoadingIndicator extends StatelessWidget {
  final double size;
  final String? message;

  const TMLoadingIndicator({
    super.key,
    this.size = 28,
    this.message,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: size,
            height: size,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              valueColor: AlwaysStoppedAnimation<Color>(tm.deepRoyalBlue),
            ),
          ),
          if (message != null) ...[
            const SizedBox(height: Spacing.xl3),
            Text(
              message!,
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textTertiary,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Premium empty state with icon, title, subtitle, and optional action.
class TMEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const TMEmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Spacing.xl8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Icon
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: tm.sapphireOverlay,
                shape: BoxShape.circle,
                border: Border.all(
                  color: tm.sapphire.withValues(alpha: 0.2),
                  width: 1,
                ),
              ),
              child: Icon(
                icon,
                size: 34,
                color: tm.sapphire.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: Spacing.xl5),
            // Title
            Text(
              title,
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: tm.textPrimary,
                letterSpacing: -0.2,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: Spacing.md),
            // Subtitle
            Text(
              subtitle,
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textTertiary,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: Spacing.xl5),
              TMPrimaryButton(
                label: actionLabel!,
                onPressed: onAction,
                width: 200,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Premium error state with retry.
class TMErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const TMErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Spacing.xl8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: tm.error.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.error_outline_rounded,
                size: 32,
                color: tm.error.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: Spacing.xl5),
            const Text(
              'Something went wrong',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: Spacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textTertiary,
                height: 1.4,
              ),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: Spacing.xl5),
              TMPrimaryButton(
                label: 'Try Again',
                onPressed: onRetry,
                width: 180,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM ANIMATED CONTAINER
// ─────────────────────────────────────────────────────────────────────────────

/// Animated container that smoothly transitions its properties.
class TMAnimatedContainer extends StatelessWidget {
  final bool isActive;
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double? borderRadius;
  final Color activeColor;
  final Color inactiveColor;
  final Color activeBorderColor;
  final Color inactiveBorderColor;

  const TMAnimatedContainer({
    super.key,
    required this.isActive,
    required this.child,
    this.padding,
    this.borderRadius,
    this.activeColor = Colors.black,
    this.inactiveColor = Colors.transparent,
    this.activeBorderColor = Colors.black,
    this.inactiveBorderColor = const Color(0xFFE5E5E0),
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeInOut,
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: isActive ? activeColor : inactiveColor,
        borderRadius: BorderRadius.circular(borderRadius ?? 20),
        border: Border.all(
          color: isActive ? activeBorderColor : inactiveBorderColor,
        ),
      ),
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PREMIUM LIST TILE
// ─────────────────────────────────────────────────────────────────────────────

/// A premium list tile with left icon, title, subtitle, and trailing chevron.
class TMListTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final Color? iconColor;

  const TMListTile({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Material(
      color: tm.brandWhite,
      borderRadius: BorderRadius.circular(RadiusTokens.xl2),
      child: InkWell(
        borderRadius: BorderRadius.circular(RadiusTokens.xl2),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(Spacing.xl3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(RadiusTokens.xl2),
            border: Border.all(color: tm.borderLight),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(Spacing.md),
                decoration: BoxDecoration(
                  color: (iconColor ?? tm.textTertiary).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(RadiusTokens.xl),
                ),
                child: Icon(
                  icon,
                  size: IconSizes.lg,
                  color: iconColor ?? tm.textSecondary,
                ),
              ),
              const SizedBox(width: Spacing.xl3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: tm.textPrimary,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle!,
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          color: tm.textTertiary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              trailing ??
                  Icon(
                    Icons.chevron_right,
                    color: tm.border,
                    size: IconSizes.lg,
                  ),
            ],
          ),
        ),
      ),
    );
  }
}
