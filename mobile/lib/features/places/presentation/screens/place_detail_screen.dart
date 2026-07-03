import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../../../features/explore/data/models/place_model.dart';
import '../../data/models/review_model.dart';
import '../../data/repository/places_repository.dart';
import '../../logic/place_detail_cubit.dart';
import '../../logic/place_detail_state.dart';
import '../../logic/reviews_cubit.dart';
import '../../logic/reviews_state.dart';
import 'write_review_sheet.dart';

class PlaceDetailScreen extends StatelessWidget {
  final String placeId;

  const PlaceDetailScreen({super.key, required this.placeId});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => PlaceDetailCubit(
        locator<PlacesRepository>(),
        placeId,
      ),
      child: _PlaceDetailView(placeId: placeId),
    );
  }
}

class _PlaceDetailView extends StatelessWidget {
  final String placeId;

  const _PlaceDetailView({required this.placeId});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Scaffold(
      backgroundColor: tm.brandWhite,
      body: BlocBuilder<PlaceDetailCubit, PlaceDetailState>(
        builder: (context, state) {
          return state.when(
            initial: () => const Center(child: TMLoadingIndicator(message: 'Loading place...')),
            loading: () => const Center(child: TMLoadingIndicator(message: 'Loading place...')),
            error: (message) => TMErrorState(message: message, onRetry: () => context.read<PlaceDetailCubit>().load()),
            loaded: (place) => _buildContent(context, tm, place),
          );
        },
      ),
    );
  }

  Widget _buildContent(BuildContext context, TourMateColors tm, PlaceModel place) {
    return CustomScrollView(
      slivers: [
        // ── Premium Photo Header ──────────────────────────
        SliverAppBar(
          expandedHeight: 320,
          pinned: true,
          backgroundColor: tm.deepNavy,
          systemOverlayStyle: SystemUiOverlayStyle.light,
          leading: Padding(
            padding: const EdgeInsets.all(Spacing.md),
            child: Container(
              decoration: BoxDecoration(
                color: tm.deepNavy.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
                border: Border.all(color: tm.brandWhite.withValues(alpha: 0.15)),
              ),
              child: IconButton(
                icon: Icon(Icons.arrow_back_rounded, color: tm.textOnDark, size: 20),
                onPressed: () => Navigator.pop(context),
              ),
            ),
          ),
          flexibleSpace: FlexibleSpaceBar(
            background: _buildPhotoHeader(tm, place),
          ),
        ),

        // ── Premium Content ────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(Spacing.xl4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildTitleSection(tm, place),
                const SizedBox(height: Spacing.xl4),
                if (place.description != null && place.description!.isNotEmpty)
                  _buildSection(tm, 'Description', place.description!),
                if (place.address != null && place.address!.isNotEmpty) ...[
                  const SizedBox(height: Spacing.xl3),
                  _buildInfoCard(
                    tm,
                    icon: Icons.location_on_outlined,
                    title: place.address!,
                    subtitle: 'Address',
                  ),
                ],
                const SizedBox(height: Spacing.xl3),
                _buildCategoryDetails(tm, place),
                if (place.lat != null && place.lng != null) ...[
                  const SizedBox(height: Spacing.xl3),
                  GestureDetector(
                    onTap: () => _openInGoogleMaps(place),
                    child: _buildInfoCard(
                      tm,
                      icon: Icons.map_outlined,
                      title: '${place.lat!.toStringAsFixed(4)}, ${place.lng!.toStringAsFixed(4)}',
                      subtitle: 'Open in Google Maps',
                      trailing: Icon(Icons.open_in_new, size: 16, color: tm.sapphire),
                      isClickable: true,
                    ),
                  ),
                ],
                if (place.phone != null && place.phone!.isNotEmpty) ...[
                  const SizedBox(height: Spacing.xl3),
                  _buildInfoCard(
                    tm,
                    icon: Icons.phone_outlined,
                    title: place.phone!,
                    subtitle: 'Phone',
                  ),
                ],
                const SizedBox(height: Spacing.xl5),
                _buildReviewsSection(place),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoCard(
    TourMateColors tm, {
    required IconData icon,
    required String title,
    String? subtitle,
    Widget? trailing,
    bool isClickable = false,
  }) {
    return Container(
      padding: const EdgeInsets.all(Spacing.xl3),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.deepNavy.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(Spacing.md),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(RadiusTokens.lg),
            ),
            child: Icon(icon, size: 18, color: tm.sapphireLight),
          ),
          const SizedBox(width: Spacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: tm.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: Spacing.xxs),
                  Text(
                    subtitle,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: isClickable ? tm.sapphire : tm.textTertiary,
                      fontWeight: isClickable ? FontWeight.w600 : FontWeight.w400,
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

  Widget _buildPhotoHeader(TourMateColors tm, PlaceModel place) {
    Widget photoWidget;
    if (place.photoUrls.isEmpty) {
      photoWidget = Container(
        color: tm.deepNavy,
        child: Center(
          child: Icon(
            Icons.image_outlined,
            size: 80,
            color: tm.textSecondary,
          ),
        ),
      );
    } else {
      photoWidget = _PhotoCarousel(photoUrls: place.photoUrls);
    }

    return Hero(
      tag: 'place-photo-${place.placeId}',
      child: photoWidget,
    );
  }

  Widget _buildTitleSection(TourMateColors tm, PlaceModel place) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Premium category badge
        Container(
          padding: Insets.chip,
          decoration: BoxDecoration(
            color: tm.sapphire.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(RadiusTokens.xl4),
            border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.category_outlined, size: 12, color: tm.sapphire),
              const SizedBox(width: Spacing.xxs),
              Text(
                place.category,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  color: tm.sapphire,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: Spacing.md),

        // Name
        Text(
          place.name,
          style: GoogleFonts.inter(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: tm.textPrimary,
            height: 1.1,
            letterSpacing: -0.5,
          ),
        ),

        const SizedBox(height: Spacing.sm),

        // Premium rating row
        Row(
          children: [
            Icon(Icons.star_rounded, size: 20, color: tm.sapphire),
            const SizedBox(width: Spacing.xs),
            Text(
              place.rating.toStringAsFixed(1),
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: tm.sapphire,
                letterSpacing: -0.3,
              ),
            ),
            if (place.reviewCount > 0) ...[
              const SizedBox(width: Spacing.xs),
              Text(
                '(${_formatCount(place.reviewCount)})',
                style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary),
              ),
            ],
            if (place.priceLevel != null && place.priceLevel! > 0) ...[
              const SizedBox(width: Spacing.xl),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: Spacing.sm, vertical: Spacing.xxs),
                decoration: BoxDecoration(
                  color: tm.sapphire.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(RadiusTokens.sm),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.attach_money, size: 13, color: tm.sapphire),
                    Text(
                      '\$' * place.priceLevel!,
                      style: GoogleFonts.inter(fontSize: 12, color: tm.sapphire, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),

        // City / country with location icon
        if (place.city != null || place.country != null) ...[
          const SizedBox(height: Spacing.xs),
          Row(
            children: [
              Icon(Icons.location_on_outlined, size: 14, color: tm.sapphireLight),
              const SizedBox(width: Spacing.xs),
              Text(
                [
                  if (place.city != null) place.city,
                  if (place.country != null) place.country,
                ].join(', '),
                style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildSection(TourMateColors tm, String title, String body) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3,
              height: 18,
              decoration: BoxDecoration(
                color: tm.sapphire,
                borderRadius: BorderRadius.circular(RadiusTokens.xxs),
              ),
            ),
            const SizedBox(width: Spacing.md),
            Text(
              title,
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: tm.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        Text(
          body,
          style: GoogleFonts.inter(
            fontSize: 14,
            color: tm.textSecondary,
            height: 1.6,
          ),
        ),
      ],
    );
  }

  Future<void> _openInGoogleMaps(PlaceModel place) async {
    final lat = place.lat;
    final lng = place.lng;
    if (lat == null || lng == null) return;

    final uri = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=$lat,$lng',
    );
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      // Fallback: try launching in browser
      try {
        await launchUrl(uri, mode: LaunchMode.platformDefault);
      } catch (_) {}
    }
  }

  Widget _buildCategoryDetails(TourMateColors tm, PlaceModel place) {
    switch (place.category.toLowerCase()) {
      case 'hotel':
        return _buildHotelDetails(tm, place);
      case 'restaurant':
        return _buildRestaurantDetails(tm, place);
      case 'attraction':
        return _buildAttractionDetails(tm, place);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildHotelDetails(TourMateColors tm, PlaceModel place) {
    final details = <Widget>[];

    if (place.starClass != null && place.starClass! > 0) {
      details.add(_buildAccentChip(tm.sapphire, Icons.star_outline, '${place.starClass}-star hotel'));
    }
    if (place.nightlyRate != null && place.nightlyRate! > 0) {
      details.add(_buildAccentChip(tm.sapphire, Icons.bed_outlined, '\$${place.nightlyRate!.toStringAsFixed(0)} / night'));
    }
    if (place.accommodationType != null && place.accommodationType!.isNotEmpty) {
      details.add(_buildAccentChip(tm.sapphire, Icons.home_outlined, place.accommodationType!));
    }

    if (details.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3, height: 18,
              decoration: BoxDecoration(color: tm.sapphire, borderRadius: BorderRadius.circular(RadiusTokens.xxs)),
            ),
            const SizedBox(width: Spacing.md),
            Text(
              'Hotel Info',
              style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.2),
            ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        Wrap(
          spacing: Spacing.md,
          runSpacing: Spacing.md,
          children: details,
        ),
      ],
    );
  }

  Widget _buildRestaurantDetails(TourMateColors tm, PlaceModel place) {
    final details = <Widget>[];

    if (place.cuisineType != null && place.cuisineType!.isNotEmpty) {
      details.add(_buildAccentChip(tm.sapphire, Icons.restaurant_outlined, place.cuisineType!));
    }

    if (details.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3, height: 18,
              decoration: BoxDecoration(color: tm.sapphire, borderRadius: BorderRadius.circular(RadiusTokens.xxs)),
            ),
            const SizedBox(width: Spacing.md),
            Text(
              'Restaurant Info',
              style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.2),
            ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        Wrap(
          spacing: Spacing.md,
          runSpacing: Spacing.md,
          children: details,
        ),
      ],
    );
  }

  Widget _buildAttractionDetails(TourMateColors tm, PlaceModel place) {
    if (place.entryFee == null || place.entryFee! <= 0) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3, height: 18,
              decoration: BoxDecoration(color: tm.sapphire, borderRadius: BorderRadius.circular(RadiusTokens.xxs)),
            ),
            const SizedBox(width: Spacing.md),
            Text(
              'Attraction Info',
              style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.2),
            ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        _buildAccentChip(tm.sapphire, Icons.monetization_on_outlined, 'Entry fee: \$${place.entryFee!.toStringAsFixed(0)}'),
      ],
    );
  }

  Widget _buildAccentChip(Color accentColor, IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl, vertical: Spacing.md),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(RadiusTokens.md),
        border: Border.all(color: accentColor.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: accentColor),
          const SizedBox(width: Spacing.sm),
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 13,
              color: accentColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _formatCount(int count) {
    if (count >= 1000) {
      return '${(count / 1000).toStringAsFixed(1)}k';
    }
    return count.toString();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // REVIEWS SECTION
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildReviewsSection(PlaceModel place) {
    return BlocProvider(
      create: (_) =>
          ReviewsCubit(locator<ApiServices>())..fetchReviews(placeId),
      child: _ReviewsSection(place: place),
    );
  }
}

// ── Reviews Section Widget ──────────────────────────────────────────────────

class _ReviewsSection extends StatelessWidget {
  final PlaceModel place;

  const _ReviewsSection({required this.place});

  List<ReviewModel> _getFilteredAndSorted(
    List<ReviewModel> reviews, {
    required int? filterRating,
    required ReviewSort sortBy,
  }) {
    // Filter first
    var result = reviews;
    if (filterRating != null) {
      result = result.where((r) => r.rating == filterRating).toList();
    }

    // Then sort
    switch (sortBy) {
      case ReviewSort.mostRecent:
        result.sort((a, b) {
          if (a.reviewDate == null && b.reviewDate == null) return 0;
          if (a.reviewDate == null) return 1;
          if (b.reviewDate == null) return -1;
          return b.reviewDate!.compareTo(a.reviewDate!);
        });
      case ReviewSort.highestRated:
        result.sort((a, b) => b.rating.compareTo(a.rating));
      case ReviewSort.lowestRated:
        result.sort((a, b) => a.rating.compareTo(b.rating));
    }
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header row
        Row(
          children: [
            Row(
              children: [
            Container(
              width: 3, height: 20,
              decoration: BoxDecoration(color: tm.sapphire, borderRadius: BorderRadius.circular(RadiusTokens.xxs)),
            ),
            const SizedBox(width: Spacing.md),
                Text(
                  'Reviews',
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.3,
                  ),
                ),
              ],
            ),
            const Spacer(),
            // Premium sapphire-accented write button
            Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _showWriteReview(context),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.md),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(RadiusTokens.lg),
                    border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.edit_outlined, color: tm.sapphireLight, size: 14),
                      const SizedBox(width: 6),
                      Text(
                        'Write',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          color: tm.brandWhite,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: Spacing.xl3),

        // Reviews list from cubit
        BlocBuilder<ReviewsCubit, ReviewsState>(
          builder: (context, state) {
            final tm = context.tm;
            return state.when(
              initial: () => const SizedBox.shrink(),
              loading: () => Padding(
                padding: const EdgeInsets.all(Spacing.xl3),
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: tm.deepNavy,
                    ),
                  ),
                ),
              ),
              loaded: (data, isSubmitting, sortBy, filterRating) {
                final filtered = _getFilteredAndSorted(
                  data.reviews,
                  filterRating: filterRating,
                  sortBy: sortBy,
                );

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (data.averageRating != null)
                      _buildSummaryCard(tm, data),

                    if (data.reviews.isNotEmpty) ...[
              const SizedBox(height: Spacing.xl3),
              // Sort / filter toolbar
                      _buildSortFilterToolbar(context, tm, data.reviews,
                          sortBy: sortBy, filterRating: filterRating),
                      const SizedBox(height: Spacing.xl),
                    ],

                    if (filtered.isEmpty) ...[
                      const SizedBox(height: Spacing.xl3),
                      _buildEmptyReviews(tm,
                        hasReviews: data.reviews.isNotEmpty,
                        filterRating: filterRating,
                      ),
                    ] else ...[
                      const SizedBox(height: Spacing.xs),
                      ...filtered.map((review) => Padding(
                        padding: const EdgeInsets.only(bottom: Spacing.xl),
                        child: _ReviewCard(
                          review: review,
                          onEdit: () => _showEditReview(context, review),
                          onDelete: () => _showDeleteConfirm(context, review),
                          onLike: () => context.read<ReviewsCubit>().toggleLike(review.reviewId),
                        ),
                      )),
                    ],
                  ],
                );
              },
              error: (message) => Padding(                      padding: const EdgeInsets.symmetric(vertical: Spacing.xl),
                      child: Row(
                        children: [
                          Icon(Icons.cloud_off, size: 16, color: tm.textTertiary),
                          const SizedBox(width: Spacing.md),
                    Expanded(                        child: Text(
                        'Could not load reviews',
                        style: TextStyle(color: tm.textTertiary, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  /// Premium sort/filter toolbar with sapphire-accented rating chips
  Widget _buildSortFilterToolbar(
    BuildContext context,
    TourMateColors tm,
    List<ReviewModel> allReviews, {
    required ReviewSort sortBy,
    required int? filterRating,
  }) {
    final cubit = context.read<ReviewsCubit>();

    return Column(
      children: [
        // Sort dropdown + clear button
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: Spacing.xl, vertical: Spacing.xs),
              decoration: BoxDecoration(
                color: tm.surface,
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
                border: Border.all(color: tm.borderLight),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<ReviewSort>(
                  value: sortBy,
                  isDense: true,
                  icon: Icon(Icons.swap_vert, size: 16, color: tm.sapphire),
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    color: tm.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: ReviewSort.mostRecent,
                      child: Text('Most Recent'),
                    ),
                    DropdownMenuItem(
                      value: ReviewSort.highestRated,
                      child: Text('Highest Rated'),
                    ),
                    DropdownMenuItem(
                      value: ReviewSort.lowestRated,
                      child: Text('Lowest Rated'),
                    ),
                  ],
                  onChanged: (val) {
                    if (val != null) cubit.setSortBy(val);
                  },
                ),
              ),
            ),
            const Spacer(),
            if (filterRating != null)
              GestureDetector(
                onTap: () => cubit.setFilterRating(null),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.md, vertical: Spacing.xs),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.close, size: 11, color: tm.sapphire),
                      const SizedBox(width: Spacing.xs),
                      Text(
                        'Clear',
                        style: GoogleFonts.inter(fontSize: 11, color: tm.sapphire, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: Spacing.sm),
        // sapphire-accented rating filter chips
        SizedBox(
          height: 34,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: 6,
            separatorBuilder: (_, _) => const SizedBox(width: Spacing.md),
            itemBuilder: (ctx, i) {
              final rating = 5 - i;
              final isAll = rating == 0;
              final selected = isAll
                  ? filterRating == null
                  : filterRating == rating;

              return GestureDetector(
                onTap: () => cubit.setFilterRating(isAll ? null : rating),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: Insets.chip,
                  decoration: BoxDecoration(
                    gradient: selected
                        ? const LinearGradient(
                            colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          )
                        : null,
                    color: selected ? null : tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.xl4),
                    border: Border.all(
                      color: selected ? tm.sapphire.withValues(alpha: 0.5) : tm.borderLight,
                      width: selected ? 1.5 : 1,
                    ),
                    boxShadow: selected ? [
                      BoxShadow(
                        color: tm.sapphire.withValues(alpha: 0.15),
                        blurRadius: 6,
                        offset: const Offset(0, 1),
                      ),
                    ] : [],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (!isAll) ...[
                        Icon(
                          Icons.star_rounded,
                          size: 13,
                          color: selected ? tm.sapphireLight : tm.sapphire,
                        ),
                        const SizedBox(width: Spacing.xxs),
                      ],
                      Text(
                        isAll ? 'All' : '$rating',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: selected ? tm.sapphireLight : tm.textSecondary,
                        ),
                      ),
                      if (!isAll) ...[
                        const SizedBox(width: Spacing.xxs),
                        Text(
                          '(${_countRating(allReviews, rating)})',
                          style: GoogleFonts.inter(
                            fontSize: 10,
                            color: selected ? tm.sapphire.withValues(alpha: 0.6) : tm.textTertiary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSummaryCard(TourMateColors tm, PlaceReviewsResponse data) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(Spacing.xl3),
      decoration: BoxDecoration(
        color: tm.sapphire.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          // Average rating (large)
          Column(
            children: [
              Text(
                data.averageRating!.toStringAsFixed(1),
                style: GoogleFonts.inter(
                  fontSize: 34,
                  fontWeight: FontWeight.w800,
                  color: tm.sapphire,
                  letterSpacing: -0.5,
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(5, (i) {
                  final star = i + 1;
                  final filled = star <= data.averageRating!.round();
                  return Icon(
                    filled ? Icons.star_rounded : Icons.star_border_rounded,
                    size: 14,
                    color: tm.sapphire,
                  );
                }),
              ),
              const SizedBox(height: 4),
              Text(
                '${data.totalReviews} review${data.totalReviews == 1 ? '' : 's'}',
                style: GoogleFonts.inter(fontSize: 12, color: tm.textSecondary, fontWeight: FontWeight.w500),
              ),
            ],
          ),
          const SizedBox(width: Spacing.xl4),
          // Premium rating distribution bars
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: List.generate(5, (i) {
                final starLevel = 5 - i;
                final count = _countRating(data.reviews, starLevel);
                final pct = data.totalReviews > 0
                    ? count / data.totalReviews
                    : 0.0;
                return Padding(
                  padding: const EdgeInsets.only(bottom: Spacing.xs),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 24,
                        child: Text(
                          '$starLevel',
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            color: tm.textTertiary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(RadiusTokens.xs),
                          child: LinearProgressIndicator(
                            value: pct,
                            minHeight: 6,
                            backgroundColor: tm.sapphire.withValues(alpha: 0.2),
                            valueColor: AlwaysStoppedAnimation(tm.sapphire),
                          ),
                        ),
                      ),
                      SizedBox(
                        width: 20,
                        child: Text(
                          '$count',
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            color: tm.textTertiary,
                            fontWeight: FontWeight.w600,
                          ),
                          textAlign: TextAlign.right,
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  int _countRating(List<ReviewModel> reviews, int rating) {
    return reviews.where((r) => r.rating == rating).length;
  }

  Widget _buildEmptyReviews(TourMateColors tm, {bool hasReviews = false, int? filterRating}) {
    final isFiltered = filterRating != null && hasReviews;
    if (isFiltered) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: Spacing.xl5),
        child: Column(
          children: [
            Icon(Icons.search_off, size: 40, color: tm.textTertiary),
            const SizedBox(height: Spacing.md),
            Text(
              'No $filterRating-star reviews',
              style: GoogleFonts.inter(fontSize: 15, color: tm.textTertiary, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            Text(
              'Try selecting a different rating filter',
              style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary),
            ),
          ],
        ),
      );
    }
    return TMEmptyState(
      icon: Icons.rate_review_outlined,
      title: 'No reviews yet',
      subtitle: 'Be the first to share your experience',
    );
  }

  void _showWriteReview(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(              borderRadius: BorderRadius.vertical(top: Radius.circular(RadiusTokens.xl5)),
      ),
      builder: (ctx) => BlocProvider.value(
        value: context.read<ReviewsCubit>(),
        child: WriteReviewSheet(              placeId: place.placeId,
              onSubmit: ({required int rating, String? comment}) async {
            final cubit = context.read<ReviewsCubit>();
            final success = await cubit.submitReview(
              placeId: place.placeId,
              rating: rating,
              comment: comment,
            );
            if (ctx.mounted) {
              Navigator.pop(ctx);
              if (success) {
                AppSnackbar.success(context, 'Review submitted!');
              } else {
                AppSnackbar.error(context, 'Failed to submit review');
              }
            }
          },
        ),
      ),
    );
  }

  void _showEditReview(BuildContext context, ReviewModel review) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => BlocProvider.value(
        value: context.read<ReviewsCubit>(),
        child: WriteReviewSheet(
          placeId: place.placeId,
          isEditing: true,
          initialRating: review.rating,
          initialComment: review.comment,
          onSubmit: ({required int rating, String? comment}) async {
            final cubit = context.read<ReviewsCubit>();
            final success = await cubit.updateReview(
              reviewId: review.reviewId,
              rating: rating,
              comment: comment,
            );
            if (ctx.mounted) {
              Navigator.pop(ctx);
              if (success) {
                AppSnackbar.success(context, 'Review updated!');
              } else {
                AppSnackbar.error(context, 'Failed to update review');
              }
            }
          },
        ),
      ),
    );
  }

  void _showDeleteConfirm(BuildContext context, ReviewModel review) {
    final tm = context.tm;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        ),
        backgroundColor: tm.brandWhite,
        titlePadding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xl3, Spacing.xl3, 0),
        contentPadding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.md, Spacing.xl3, 0),
        actionsPadding: const EdgeInsets.fromLTRB(Spacing.sm, Spacing.sm, Spacing.sm, Spacing.sm),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: tm.error.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.delete_outline, size: 18, color: tm.error),
            ),
            const SizedBox(width: 10),
            Text(
              'Delete Review',
              style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 17, color: tm.textPrimary, letterSpacing: -0.2),
            ),
          ],
        ),
        content: Text(
          'Are you sure you want to delete this review? This cannot be undone.',
          style: GoogleFonts.inter(fontSize: 14, color: tm.textSecondary, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('Cancel', style: GoogleFonts.inter(color: tm.textTertiary, fontWeight: FontWeight.w600, fontSize: 14)),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final cubit = context.read<ReviewsCubit>();
              final success = await cubit.deleteReview(review.reviewId);
              if (!context.mounted) return;
              if (success) {
                AppSnackbar.info(context, 'Review deleted');
              } else {
                AppSnackbar.error(context, 'Failed to delete review');
              }
            },
            style: TextButton.styleFrom(
              backgroundColor: tm.error.withValues(alpha: 0.08),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('Delete', style: GoogleFonts.inter(color: tm.error, fontWeight: FontWeight.w700, fontSize: 14)),
          ),
        ],
      ),
    );
  }
}

// ── Premium Review Card ─────────────────────────────────────────────────────

class _ReviewCard extends StatelessWidget {
  final ReviewModel review;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onLike;

  const _ReviewCard({
    required this.review,
    required this.onEdit,
    required this.onDelete,
    required this.onLike,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(Spacing.xl3),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.deepNavy.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: sapphire stars + date + popup menu
          Row(
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(5, (i) {
                  return Icon(
                    i < review.rating
                        ? Icons.star_rounded
                        : Icons.star_border_rounded,
                    size: 16,
                    color: tm.sapphire,
                  );
                }),
              ),
              const SizedBox(width: 6),
              Text(
                review.rating.toString(),
                style: GoogleFonts.inter(fontSize: 11, color: tm.sapphire, fontWeight: FontWeight.w700),
              ),
              const Spacer(),
              if (review.reviewDate != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.sm, vertical: Spacing.xxs),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(RadiusTokens.sm),
                  ),
                  child: Text(
                    _formatDate(review.reviewDate!),
                    style: GoogleFonts.inter(fontSize: 10, color: tm.sapphire, fontWeight: FontWeight.w600),
                  ),
                ),
              const SizedBox(width: 4),
              // Popup menu
              PopupMenuButton<String>(
                padding: EdgeInsets.zero,
                icon: Container(
                  padding: const EdgeInsets.all(Spacing.xxs),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.sm),
                  ),
                  child: Icon(Icons.more_horiz, size: 16, color: tm.textTertiary),
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.md),
                ),
                onSelected: (value) {
                  if (value == 'edit') onEdit();
                  if (value == 'delete') onDelete();
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'edit',
                    child: Row(
                      children: [
                        Icon(Icons.edit_outlined, size: 18, color: tm.textPrimary),
                        const SizedBox(width: Spacing.lg),
                        const Text('Edit'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline, size: 18, color: tm.error),
                        const SizedBox(width: Spacing.lg),
                        Text('Delete', style: TextStyle(color: tm.error)),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),

          // Comment
          if (review.comment != null && review.comment!.isNotEmpty) ...[
            const SizedBox(height: Spacing.sm),
            Text(
              review.comment!,
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textSecondary,
                height: 1.5,
              ),
            ),
          ],

          // Divider
          const SizedBox(height: Spacing.md),
          Container(
            height: 1,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [tm.divider.withValues(alpha: 0), tm.divider, tm.divider.withValues(alpha: 0)],
              ),
            ),
          ),
          const SizedBox(height: Spacing.md),

          // Footer with like button + user avatar + name
          Row(
            children: [
              // sapphire-accented like button
              GestureDetector(
                onTap: onLike,
                behavior: HitTestBehavior.opaque,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.md, vertical: Spacing.xs),
                  decoration: BoxDecoration(
                    color: review.likedByUser
                        ? tm.error.withValues(alpha: 0.08)
                        : tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                    border: Border.all(
                      color: review.likedByUser
                          ? tm.error.withValues(alpha: 0.2)
                          : tm.sapphire.withValues(alpha: 0.15),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 200),
                        transitionBuilder: (child, anim) => ScaleTransition(
                          scale: anim,
                          child: child,
                        ),
                        child: Icon(
                          review.likedByUser
                              ? Icons.favorite
                              : Icons.favorite_border,
                          key: ValueKey(review.likedByUser),
                          size: 13,
                          color: review.likedByUser
                              ? tm.error
                              : tm.sapphire,
                        ),
                      ),
                      const SizedBox(width: Spacing.xs),
                      Text(
                        '${review.likesCount}',
                        style: GoogleFonts.inter(
                          fontSize: 11,
                          color: review.likedByUser ? tm.error : tm.sapphire,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: Spacing.xl),
              // User avatar with black/sapphire gradient
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  shape: BoxShape.circle,
                  border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 1),
                ),
                alignment: Alignment.center,
                child: Text(
                  review.initials,
                  style: GoogleFonts.inter(
                    fontSize: 8,
                    fontWeight: FontWeight.w700,
                    color: tm.sapphireLight,
                  ),
                ),
              ),
              const SizedBox(width: Spacing.sm),
              Expanded(
                child: Text(
                  review.displayName,
                  style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary, fontWeight: FontWeight.w500),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      final months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ];
      return '${months[dt.month - 1]} ${dt.day}, ${dt.year}';
    } catch (_) {
      return dateStr.length >= 10 ? dateStr.substring(0, 10) : dateStr;
    }
  }
}

// ── Photo Carousel ────────────────────────────────────────────────────────────

class _PhotoCarousel extends StatefulWidget {
  final List<String> photoUrls;

  const _PhotoCarousel({required this.photoUrls});

  @override
  State<_PhotoCarousel> createState() => _PhotoCarouselState();
}

class _PhotoCarouselState extends State<_PhotoCarousel> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Stack(
      fit: StackFit.expand,
      children: [
        PageView.builder(
          controller: _pageController,
          itemCount: widget.photoUrls.length,
          onPageChanged: (index) => setState(() => _currentPage = index),
          itemBuilder: (_, index) => Image.network(
            widget.photoUrls[index],
            fit: BoxFit.cover,
            loadingBuilder: (_, child, progress) {
              if (progress == null) return child;
              return Container(color: tm.deepNavy);
            },
            errorBuilder: (_, _, _) => Container(color: tm.deepNavy),
          ),
        ),
        // Premium gradient overlay
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Colors.transparent,
                Color(0x99000000),
              ],
            ),
          ),
        ),
        // page indicator dots
        if (widget.photoUrls.length > 1)
          Positioned(
            bottom: 20,
            left: 0,
            right: 0,
            child: Center(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  widget.photoUrls.length,
                  (i) => _PageDot(isActive: i == _currentPage),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _PageDot extends StatelessWidget {
  final bool isActive;

  const _PageDot({required this.isActive});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      margin: const EdgeInsets.symmetric(horizontal: 4),
      width: isActive ? 20 : 7,
      height: 7,
      decoration: BoxDecoration(
        color: isActive ? tm.sapphire : tm.brandWhite.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(4),
        boxShadow: isActive ? [
          BoxShadow(
            color: tm.sapphire.withValues(alpha: 0.4),
            blurRadius: 6,
            offset: const Offset(0, 1),
          ),
        ] : [],
      ),
    );
  }
}
