import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../features/explore/data/models/place_model.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';

class PlaceDetailScreen extends StatefulWidget {
  final String placeId;

  const PlaceDetailScreen({super.key, required this.placeId});

  @override
  State<PlaceDetailScreen> createState() => _PlaceDetailScreenState();
}

class _PlaceDetailScreenState extends State<PlaceDetailScreen> {
  PlaceModel? _place;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPlace();
  }

  Future<void> _loadPlace() async {
    try {
      final api = locator<ApiServices>();
      final data = await api.getPlaceDetail(widget.placeId);
      if (mounted) {
        setState(() {
          _place = PlaceModel.fromJson(data);
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
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
              _error!,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _loadPlace,
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

  Widget _buildContent() {
    final place = _place!;
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
                if (place.lat != null && place.lon != null) ...[
                  const SizedBox(height: 16),
                  _buildLocationSection(place),
                ],
                const SizedBox(height: 40),
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
                '${'\$' * place.priceLevel!}',
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
                  '${place.lat!.toStringAsFixed(4)}, ${place.lon!.toStringAsFixed(4)}',
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
}
