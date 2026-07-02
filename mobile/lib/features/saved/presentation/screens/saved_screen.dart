import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../../../features/explore/data/models/place_model.dart';
import '../../data/models/saved_place_item.dart';
import '../../data/repository/saved_repository.dart';
import '../../logic/saved_cubit.dart';
import '../../logic/saved_state.dart';

class SavedScreen extends StatelessWidget {
  const SavedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => SavedCubit(locator<SavedRepository>())..load(),
      child: const _SavedView(),
    );
  }
}

class _SavedView extends StatelessWidget {
  const _SavedView();

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Scaffold(
      backgroundColor: tm.nearWhite,
      appBar: AppBar(
        backgroundColor: tm.pureWhite,
        surfaceTintColor: tm.pureWhite,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        title: Row(
          children: [
            Container(
              width: 3,
              height: 20,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [tm.sapphire, tm.sapphireSurface],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: Spacing.lg),
            Text(
              'Saved Places',
              style: GoogleFonts.inter(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: tm.textPrimary,
                letterSpacing: -0.3,
              ),
            ),
          ],
        ),
        centerTitle: false,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: tm.divider, height: 0.5),
        ),
      ),
      body: BlocBuilder<SavedCubit, SavedState>(
        builder: (context, state) {
          return state.when(
            initial: () => const SizedBox(),
            loading: () => const Center(
              child: TMLoadingIndicator(message: 'Loading saved places...'),
            ),
            error: (message) => TMErrorState(
              message: message,
              onRetry: () => context.read<SavedCubit>().load(),
            ),
            loaded: (items) => _buildLoaded(context, items),
          );
        },
      ),
    );
  }

  Widget _buildLoaded(BuildContext context, List<SavedPlaceItem> items) {
    if (items.isEmpty) {
      return const Center(
        child: TMEmptyState(
          icon: Icons.favorite_border,
          title: 'No saved places yet',
          subtitle: 'Tap the heart icon on any place to save it here',
        ),
      );
    }

    return RefreshIndicator(
      color: context.tm.textPrimary,
      onRefresh: () => context.read<SavedCubit>().refresh(),
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          Spacing.xl3,
          Spacing.md,
          Spacing.xl3,
          Spacing.xl5,
        ),
        itemCount: items.length,
        separatorBuilder: (_, _) => const SizedBox(height: Spacing.xl3),
        itemBuilder: (context, index) {
          final item = items[index];
          return _SavedPlaceCard(
            place: item.place,
            onTap: () {
              if (item.place.placeId.isNotEmpty) {
                Navigator.pushNamed(
                  context,
                  '/place-detail',
                  arguments: item.place.placeId,
                );
              }
            },
            onUnsave: () => _showUnsaveDialog(context, item),
          );
        },
      ),
    );
  }

  void _showUnsaveDialog(BuildContext context, SavedPlaceItem item) {
    final tm = context.tm;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        ),
        backgroundColor: tm.pureWhite,
        titlePadding: const EdgeInsets.fromLTRB(
          Spacing.xl3,
          Spacing.xl3,
          Spacing.xl3,
          0,
        ),
        contentPadding: const EdgeInsets.fromLTRB(
          Spacing.xl3,
          Spacing.md,
          Spacing.xl3,
          0,
        ),
        actionsPadding: const EdgeInsets.fromLTRB(
          Spacing.sm,
          Spacing.sm,
          Spacing.sm,
          Spacing.sm,
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(Spacing.md),
              decoration: BoxDecoration(
                color: tm.sapphire.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(Icons.favorite_border, size: 18, color: tm.sapphire),
            ),
            const SizedBox(width: Spacing.lg),
            Text(
              'Remove saved place',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.w700,
                fontSize: 17,
                color: tm.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ],
        ),
        content: Text(
          'Are you sure you want to remove "${item.place.name}" from your saved places?',
          style: GoogleFonts.inter(
            fontSize: 14,
            color: tm.textSecondary,
            height: 1.5,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(
                horizontal: Spacing.xl3,
                vertical: Spacing.xl,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
              ),
            ),
            child: Text(
              'Cancel',
              style: GoogleFonts.inter(
                color: tm.textTertiary,
                fontWeight: FontWeight.w600,
                fontSize: 14,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.read<SavedCubit>().unsave(item.savedPlaceId);
            },
            style: TextButton.styleFrom(
              backgroundColor: tm.error.withValues(alpha: 0.08),
              padding: const EdgeInsets.symmetric(
                horizontal: Spacing.xl3,
                vertical: Spacing.xl,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
              ),
            ),
            child: Text(
              'Remove',
              style: GoogleFonts.inter(
                color: tm.error,
                fontWeight: FontWeight.w700,
                fontSize: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SavedPlaceCard extends StatelessWidget {
  final PlaceModel place;
  final VoidCallback onTap;
  final VoidCallback onUnsave;

  const _SavedPlaceCard({
    required this.place,
    required this.onTap,
    required this.onUnsave,
  });

  String get _categoryLabel {
    switch (place.category.toLowerCase()) {
      case 'hotel':
        return 'Hotel';
      case 'restaurant':
        return 'Restaurant';
      case 'attraction':
        return 'Attraction';
      default:
        return place.category.isEmpty ? 'Place' : place.category;
    }
  }

  String get _locationText {
    final parts = <String>[];
    if (place.city != null && place.city!.isNotEmpty) parts.add(place.city!);
    if (place.country != null && place.country!.isNotEmpty) {
      parts.add(place.country!);
    }
    return parts.join(', ');
  }

  String get _descriptionSnippet {
    final desc = place.description;
    if (desc == null || desc.isEmpty) return '';
    if (desc.length <= 120) return desc;
    return '${desc.substring(0, 117)}...';
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Material(
      color: tm.pureWhite,
      borderRadius: BorderRadius.circular(RadiusTokens.xl3),
      child: InkWell(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            border: Border.all(color: tm.borderLight),
            boxShadow: [
              BoxShadow(
                color: tm.pureBlack.withValues(alpha: 0.04),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Photo with save button ════════════
              if (place.hasPhoto)
                Hero(
                  tag: 'place-photo-${place.placeId}',
                  child: SizedBox(
                    height: 170,
                    width: double.infinity,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.network(
                          place.firstPhoto,
                          fit: BoxFit.cover,
                          loadingBuilder: (_, child, progress) {
                            if (progress == null) return child;
                            return Container(
                              color: tm.surface,
                              child: const Center(
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.black26,
                                ),
                              ),
                            );
                          },
                          errorBuilder: (_, _, _) => Container(
                            color: tm.surface,
                            child: Icon(
                              Icons.image,
                              color: tm.textTertiary,
                              size: 48,
                            ),
                          ),
                        ),
                        // Gradient overlay at bottom
                        Positioned(
                          bottom: 0,
                          left: 0,
                          right: 0,
                          height: 60,
                          child: Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                begin: Alignment.bottomCenter,
                                end: Alignment.topCenter,
                                colors: [
                                  tm.pureBlack.withValues(alpha: 0.4),
                                  Colors.transparent,
                                ],
                              ),
                            ),
                          ),
                        ),
                        // save button
                        Positioned(
                          top: 10,
                          right: 10,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(Spacing.xl4),
                              onTap: onUnsave,
                              child: Container(
                                padding: const EdgeInsets.all(Spacing.lg),
                                decoration: BoxDecoration(
                                  color: tm.pureWhite.withValues(alpha: 0.9),
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: tm.sapphire.withValues(alpha: 0.5),
                                    width: 1.5,
                                  ),
                                ),                child: Icon(
                  Icons.favorite,
                  size: 20,
                  color: tm.deepRoyalBlue,
                ),
                              ),
                            ),
                          ),
                        ),
                        // Rating badge on photo
                        if (place.rating > 0)
                          Positioned(
                            bottom: 10,
                            left: 10,
                            child: TMRatingBadge(
                              rating: place.rating,
                              reviewCount: place.reviewCount > 0
                                  ? place.reviewCount
                                  : null,
                            ),
                          ),
                      ],
                    ),
                  ),
                )
              else
                Hero(
                  tag: 'place-photo-${place.placeId}',
                  child: Container(
                    height: 140,
                    width: double.infinity,
                    color: tm.surface,
                    child: Stack(
                      children: [
                        Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.image_outlined,
                                size: 40,
                                color: tm.borderLight,
                              ),
                              const SizedBox(height: Spacing.md),
                              Text(
                                'No image available',
                                style: GoogleFonts.inter(
                                  fontSize: 12,
                                  color: tm.textTertiary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Positioned(
                          top: 10,
                          right: 10,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(Spacing.xl4),
                              onTap: onUnsave,
                              child: Container(
                                padding: const EdgeInsets.all(Spacing.lg),
                                decoration: BoxDecoration(
                                  color: tm.pureWhite.withValues(alpha: 0.9),
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: tm.sapphire.withValues(alpha: 0.5),
                                    width: 1.5,
                                  ),
                                ),
                                child: Icon(
                                  Icons.favorite,
                                  size: 20,
                                  color: tm.deepRoyalBlue,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // ── Card content ═══════════════════════════
              Padding(
                padding: const EdgeInsets.all(Spacing.xl3),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Category + rating row
                    Row(
                      children: [
                        TMBadge(
                          label: _categoryLabel,
                          icon: Icons.sell_outlined,
                        ),
                        const Spacer(),
                        if (place.rating > 0 && !place.hasPhoto)
                          TMRatingBadge(rating: place.rating),
                      ],
                    ),
                    const SizedBox(height: Spacing.sm),

                    // Name
                    Text(
                      place.name,
                      style: GoogleFonts.inter(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: tm.textPrimary,
                        letterSpacing: -0.2,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),

                    // Description
                    if (_descriptionSnippet.isNotEmpty) ...[
                      const SizedBox(height: Spacing.sm),
                      Text(
                        _descriptionSnippet,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: tm.textSecondary,
                          height: 1.35,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],

                    // Location
                    if (_locationText.isNotEmpty) ...[
                      const SizedBox(height: Spacing.sm),
                      Row(
                        children: [
                          Icon(
                            Icons.location_on_outlined,
                            size: 14,
                            color: tm.textTertiary,
                          ),
                          const SizedBox(width: Spacing.xs),
                          Expanded(
                            child: Text(
                              _locationText,
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                color: tm.textTertiary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
