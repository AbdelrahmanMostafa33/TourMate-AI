import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
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
    return Scaffold(
      backgroundColor: Colors.white,
      body: BlocBuilder<PlaceDetailCubit, PlaceDetailState>(
        builder: (context, state) {
          return state.when(
            initial: () => const Center(child: CircularProgressIndicator()),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (message) => _buildError(context, message),
            loaded: (place) => _buildContent(context, place),
          );
        },
      ),
    );
  }

  Widget _buildError(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            const Text(
              'Could not load place',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => context.read<PlaceDetailCubit>().load(),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.black,
                foregroundColor: Colors.white,
              ),
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, PlaceModel place) {
    return CustomScrollView(
      slivers: [
        // ── Photo Header ─────────────────────────────────
        SliverAppBar(
          expandedHeight: 300,
          pinned: true,
          backgroundColor: Colors.black,
          systemOverlayStyle: SystemUiOverlayStyle.light,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
          flexibleSpace: FlexibleSpaceBar(
            background: _buildPhotoHeader(place),
          ),
        ),

        // ── Content ───────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildTitleSection(place),
                const SizedBox(height: 20),
                if (place.description != null && place.description!.isNotEmpty)
                  _buildSection('Description', place.description!),
                if (place.address != null && place.address!.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _buildAddressSection(place),
                ],
                const SizedBox(height: 16),
                _buildCategoryDetails(place),
                if (place.lat != null && place.lng != null) ...[
                  const SizedBox(height: 16),
                  _buildLocationSection(place),
                ],
                const SizedBox(height: 24),
                _buildReviewsSection(place),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPhotoHeader(PlaceModel place) {
    if (place.hasPhoto) {
      return Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            place.firstPhoto,
            fit: BoxFit.cover,
            loadingBuilder: (_, child, progress) {
              if (progress == null) return child;
              return Container(color: Colors.grey[900]);
            },
            errorBuilder: (_, _, _) =>
                Container(color: Colors.grey[900]),
          ),
          // Gradient overlay for readability
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.transparent,
                  Colors.black.withValues(alpha: 0.6),
                ],
              ),
            ),
          ),
        ],
      );
    }
    return Container(
      color: Colors.grey[900],
      child: Center(
        child: Icon(
          Icons.image_outlined,
          size: 80,
          color: Colors.grey[700],
        ),
      ),
    );
  }

  Widget _buildTitleSection(PlaceModel place) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Category badge
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            '${place.categoryEmoji}  ${place.category}',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[700],
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        const SizedBox(height: 12),

        // Name
        Text(
          place.name,
          style: const TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: Colors.black,
            height: 1.1,
          ),
        ),

        const SizedBox(height: 8),

        // Rating row
        Row(
          children: [
            Icon(Icons.star_rounded, size: 20, color: Colors.amber[700]),
            const SizedBox(width: 4),
            Text(
              place.rating.toStringAsFixed(1),
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: Colors.amber[800],
              ),
            ),
            if (place.reviewCount > 0) ...[
              const SizedBox(width: 4),
              Text(
                '(${_formatCount(place.reviewCount)})',
                style: TextStyle(fontSize: 13, color: Colors.grey[500]),
              ),
            ],
            if (place.priceLevel != null && place.priceLevel! > 0) ...[
              const SizedBox(width: 12),
              Icon(Icons.attach_money, size: 16, color: Colors.grey[500]),
              Text(
                '\$' * place.priceLevel!,
                style: TextStyle(fontSize: 13, color: Colors.grey[500]),
              ),
            ],
          ],
        ),

        // City / country
        if (place.city != null || place.country != null) ...[
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(Icons.location_on_outlined, size: 15, color: Colors.grey[400]),
              const SizedBox(width: 4),
              Text(
                [
                  if (place.city != null) place.city,
                  if (place.country != null) place.country,
                ].join(', '),
                style: TextStyle(fontSize: 13, color: Colors.grey[500]),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildSection(String title, String body) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: Colors.black,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          body,
          style: TextStyle(
            fontSize: 14,
            color: Colors.grey[700],
            height: 1.5,
          ),
        ),
      ],
    );
  }

  Widget _buildAddressSection(PlaceModel place) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.location_on_outlined, color: Colors.grey[600], size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              place.address!,
              style: TextStyle(fontSize: 13, color: Colors.grey[700]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationSection(PlaceModel place) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.map_outlined, color: Colors.grey[600], size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${place.lat!.toStringAsFixed(4)}, ${place.lng!.toStringAsFixed(4)}',
                  style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                ),
                const SizedBox(height: 2),
                Text(
                  'Map coordinates',
                  style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                ),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: Colors.grey[400], size: 18),
        ],
      ),
    );
  }

  Widget _buildCategoryDetails(PlaceModel place) {
    switch (place.category.toLowerCase()) {
      case 'hotel':
        return _buildHotelDetails(place);
      case 'restaurant':
        return _buildRestaurantDetails(place);
      case 'attraction':
        return _buildAttractionDetails(place);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildHotelDetails(PlaceModel place) {
    final details = <Widget>[];

    if (place.starClass != null && place.starClass! > 0) {
      details.add(_buildInfoChip(
        Icons.star_outline,
        '${place.starClass}-star hotel',
      ));
    }
    if (place.nightlyRate != null && place.nightlyRate! > 0) {
      details.add(_buildInfoChip(
        Icons.bed_outlined,
        '\$${place.nightlyRate!.toStringAsFixed(0)} / night',
      ));
    }
    if (place.accommodationType != null && place.accommodationType!.isNotEmpty) {
      details.add(_buildInfoChip(
        Icons.home_outlined,
        place.accommodationType!,
      ));
    }

    if (details.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Hotel Info',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.black),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: details,
        ),
      ],
    );
  }

  Widget _buildRestaurantDetails(PlaceModel place) {
    final details = <Widget>[];

    if (place.cuisineType != null && place.cuisineType!.isNotEmpty) {
      details.add(_buildInfoChip(
        Icons.restaurant_outlined,
        place.cuisineType!,
      ));
    }

    if (details.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Restaurant Info',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.black),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: details,
        ),
      ],
    );
  }

  Widget _buildAttractionDetails(PlaceModel place) {
    if (place.entryFee == null || place.entryFee! <= 0) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Attraction Info',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.black),
        ),
        const SizedBox(height: 10),
        _buildInfoChip(Icons.monetization_on_outlined, 'Entry fee: \$${place.entryFee!.toStringAsFixed(0)}'),
      ],
    );
  }

  Widget _buildInfoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.grey[600]),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[700],
              fontWeight: FontWeight.w500,
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header row
        Row(
          children: [
            const Text(
              'Reviews',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Colors.black,
              ),
            ),
            const Spacer(),
            // Write a review button
            Material(
              color: Colors.black,
              borderRadius: BorderRadius.circular(10),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _showWriteReview(context),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 8,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.edit_outlined,
                          color: Colors.white, size: 14),
                      const SizedBox(width: 6),
                      Text(
                        'Write',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[100],
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

        const SizedBox(height: 16),

        // Reviews list from cubit
        BlocBuilder<ReviewsCubit, ReviewsState>(
          builder: (context, state) {
            return state.when(
              initial: () => const SizedBox.shrink(),
              loading: () => const Padding(
                padding: EdgeInsets.all(16),
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.black,
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
                      _buildSummaryCard(data),

                    if (data.reviews.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      // Sort / filter toolbar
                      _buildSortFilterToolbar(context, data.reviews,
                          sortBy: sortBy, filterRating: filterRating),
                      const SizedBox(height: 12),
                    ],

                    if (filtered.isEmpty) ...[
                      const SizedBox(height: 16),
                      _buildEmptyReviews(
                        hasReviews: data.reviews.isNotEmpty,
                        filterRating: filterRating,
                      ),
                    ] else ...[
                      const SizedBox(height: 4),
                      ...filtered.map((review) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: _ReviewCard(
                          review: review,
                          onEdit: () => _showEditReview(context, review),
                          onDelete: () => _showDeleteConfirm(context, review),
                        ),
                      )),
                    ],
                  ],
                );
              },
              error: (message) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Row(
                  children: [
                    Icon(Icons.cloud_off, size: 16, color: Colors.grey[400]),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Could not load reviews',
                        style: TextStyle(color: Colors.grey[500], fontSize: 13),
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

  /// Sort/filter toolbar with sort dropdown + rating filter chips
  Widget _buildSortFilterToolbar(
    BuildContext context,
    List<ReviewModel> allReviews, {
    required ReviewSort sortBy,
    required int? filterRating,
  }) {
    final cubit = context.read<ReviewsCubit>();

    return Column(
      children: [
        // Sort dropdown + filter chips header
        Row(
          children: [
            // Sort dropdown
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<ReviewSort>(
                  value: sortBy,
                  isDense: true,
                  icon: Icon(Icons.swap_vert,
                      size: 16, color: Colors.grey[600]),
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[700],
                    fontWeight: FontWeight.w500,
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
                    if (val != null) {
                      cubit.setSortBy(val);
                    }
                  },
                ),
              ),
            ),
            const Spacer(),
            // Active filter count text
            if (filterRating != null)
              GestureDetector(
                onTap: () => cubit.setFilterRating(null),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.close, size: 12, color: Colors.grey[600]),
                      const SizedBox(width: 4),
                      Text(
                        'Clear',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 10),
        // Rating filter chips (horizontal scrollable row)
        SizedBox(
          height: 32,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: 6,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (ctx, i) {
              final rating = 5 - i;
              final isAll = rating == 0;
              final selected = isAll
                  ? filterRating == null
                  : filterRating == rating;

              return GestureDetector(
                onTap: () {
                  cubit.setFilterRating(isAll ? null : rating);
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color:
                        selected ? Colors.black : Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: selected
                          ? Colors.black
                          : Colors.grey.shade200,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (!isAll) ...[
                        Icon(
                          Icons.star_rounded,
                          size: 13,
                          color:
                              selected ? Colors.amber[200] : Colors.amber[700],
                        ),
                        const SizedBox(width: 3),
                      ],
                      Text(
                        isAll ? 'All' : '$rating',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: selected ? Colors.white : Colors.grey[700],
                        ),
                      ),
                      if (!isAll) ...[
                        const SizedBox(width: 3),
                        Text(
                          '(${_countRating(allReviews, rating)})',
                          style: TextStyle(
                            fontSize: 10,
                            color: selected
                                ? Colors.white70
                                : Colors.grey[400],
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

  Widget _buildSummaryCard(PlaceReviewsResponse data) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.amber.shade50,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.amber.shade100),
      ),
      child: Row(
        children: [
          // Average rating (large)
          Column(
            children: [
              Text(
                data.averageRating!.toStringAsFixed(1),
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: Colors.amber[800],
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
                    color: Colors.amber[700],
                  );
                }),
              ),
              const SizedBox(height: 4),
              Text(
                '${data.totalReviews} review${data.totalReviews == 1 ? '' : 's'}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ),
          const SizedBox(width: 20),
          // Rating distribution bars
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
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 24,
                        child: Text(
                          '$starLevel',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey[500],
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: pct,
                            minHeight: 6,
                            backgroundColor: Colors.amber.shade100,
                            valueColor:
                                AlwaysStoppedAnimation(Colors.amber[700]!),
                          ),
                        ),
                      ),
                      SizedBox(
                        width: 20,
                        child: Text(
                          '$count',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey[400],
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

  Widget _buildEmptyReviews({bool hasReviews = false, int? filterRating}) {
    final isFiltered = filterRating != null && hasReviews;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Column(
        children: [
          Icon(
            isFiltered ? Icons.search_off : Icons.rate_review_outlined,
            size: 40,
            color: Colors.grey[300],
          ),
          const SizedBox(height: 12),
          Text(
            isFiltered ? 'No $filterRating-star reviews' : 'No reviews yet',
            style: TextStyle(
              fontSize: 15,
              color: Colors.grey[500],
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            isFiltered
                ? 'Try selecting a different rating filter'
                : 'Be the first to share your experience',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[400],
            ),
          ),
        ],
      ),
    );
  }

  void _showWriteReview(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
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
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Review submitted!'),
                    duration: Duration(seconds: 2),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Failed to submit review'),
                    backgroundColor: Colors.red,
                  ),
                );
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
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Review updated!'),
                    duration: Duration(seconds: 2),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Failed to update review'),
                    backgroundColor: Colors.red,
                  ),
                );
              }
            }
          },
        ),
      ),
    );
  }

  void _showDeleteConfirm(BuildContext context, ReviewModel review) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: const Text('Delete Review'),
        content: const Text('Are you sure you want to delete this review? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text(
              'Cancel',
              style: TextStyle(color: Colors.grey),
            ),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final cubit = context.read<ReviewsCubit>();
              final success = await cubit.deleteReview(review.reviewId);
              if (!context.mounted) return;
              if (success) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Review deleted'),
                    duration: Duration(seconds: 2),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Failed to delete review'),
                    backgroundColor: Colors.red,
                  ),
                );
              }
            },
            child: const Text(
              'Delete',
              style: TextStyle(
                color: Colors.red,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Single Review Card ──────────────────────────────────────────────────────

class _ReviewCard extends StatelessWidget {
  final ReviewModel review;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _ReviewCard({
    required this.review,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: star rating + date + popup menu
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
                    color: Colors.amber[700],
                  );
                }),
              ),
              const SizedBox(width: 8),
              Text(
                review.rating.toString(),
                style: TextStyle(fontSize: 11, color: Colors.grey[500], fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              if (review.reviewDate != null)
                Text(
                  _formatDate(review.reviewDate!),
                  style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                ),
              const SizedBox(width: 4),
              // Popup menu for edit/delete
              PopupMenuButton<String>(
                padding: EdgeInsets.zero,
                icon: Icon(Icons.more_horiz, size: 18, color: Colors.grey[400]),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                onSelected: (value) {
                  if (value == 'edit') onEdit();
                  if (value == 'delete') onDelete();
                },
                itemBuilder: (_) => [
                  const PopupMenuItem(
                    value: 'edit',
                    child: Row(
                      children: [
                        Icon(Icons.edit_outlined, size: 18, color: Colors.black87),
                        SizedBox(width: 10),
                        Text('Edit'),
                      ],
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline, size: 18, color: Colors.red),
                        SizedBox(width: 10),
                        Text('Delete', style: TextStyle(color: Colors.red)),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),

          // Comment
          if (review.comment != null && review.comment!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              review.comment!,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[700],
                height: 1.4,
              ),
            ),
          ],

          // Footer with user avatar + name
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.favorite_border, size: 12, color: Colors.grey[400]),
              const SizedBox(width: 4),
              Text(
                '${review.likesCount}',
                style: TextStyle(fontSize: 11, color: Colors.grey[400]),
              ),
              const SizedBox(width: 12),
              // User avatar circle
              CircleAvatar(
                radius: 10,
                backgroundColor: Colors.grey.shade300,
                child: Text(
                  review.initials,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  review.displayName,
                  style: TextStyle(fontSize: 11, color: Colors.grey[400]),
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
