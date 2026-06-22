import 'package:flutter/material.dart';

import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../explore/data/models/place_model.dart';

class SavedScreen extends StatefulWidget {
  const SavedScreen({super.key});

  @override
  State<SavedScreen> createState() => _SavedScreenState();
}

class _SavedScreenState extends State<SavedScreen> {
  final ApiServices _api = locator<ApiServices>();
  List<({String savedPlaceId, PlaceModel place})> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final raw = await _api.getSavedPlaces();
      final list = (raw as List<dynamic>).cast<Map<String, dynamic>>();
      final items = list.map((e) {
        final placeData = e['place'] as Map<String, dynamic>;
        return (
          savedPlaceId: e['saved_place_id'] as String? ?? '',
          place: PlaceModel.fromJson(placeData),
        );
      }).toList();
      if (mounted) setState(() { _items = items; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _unsave(String savedPlaceId) async {
    try {
      await _api.unsavePlace(savedPlaceId);
      setState(() => _items.removeWhere((i) => i.savedPlaceId == savedPlaceId));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'Saved Places',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.black),
        ),
        centerTitle: false,
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Colors.black));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.cloud_off, size: 64, color: Colors.grey[300]),
              const SizedBox(height: 16),
              Text("Couldn't load saved places",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.grey[800])),
              const SizedBox(height: 8),
              Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: Colors.grey[600], fontSize: 13)),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _load,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black, foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
                child: const Text('Try Again'),
              ),
            ],
          ),
        ),
      );
    }
    if (_items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.favorite_border, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 16),
            Text('No saved places yet',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.grey[800])),
            const SizedBox(height: 8),
            Text('Tap the heart icon on any place to save it here',
                style: TextStyle(color: Colors.grey[600], fontSize: 13)),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: Colors.black,
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        itemCount: _items.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final item = _items[index];
          return _SavedPlaceCard(
            place: item.place,
            onTap: () {
              if (item.place.id.isNotEmpty) {
                Navigator.pushNamed(context, '/place-detail', arguments: item.place.id);
              }
            },
            onUnsave: () => _unsave(item.savedPlaceId),
          );
        },
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
      case 'hotel': return 'Hotel';
      case 'restaurant': return 'Restaurant';
      case 'attraction': return 'Attraction';
      default: return place.category.isEmpty ? 'Place' : place.category;
    }
  }

  Color get _categoryColor {
    switch (place.category.toLowerCase()) {
      case 'hotel': return const Color(0xFF2D3436);
      case 'restaurant': return const Color(0xFF636E72);
      case 'attraction': return const Color(0xFF0984E3);
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.grey.shade200),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Photo with heart
              if (place.hasPhoto)
                SizedBox(
                  height: 160,
                  width: double.infinity,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.network(place.firstPhoto, fit: BoxFit.cover,
                        loadingBuilder: (_, child, progress) {
                          if (progress == null) return child;
                          return Container(color: Colors.grey[100], child: const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black26)));
                        },
                        errorBuilder: (_, _, _) => Container(color: Colors.grey[100], child: Icon(Icons.image, color: Colors.grey[300], size: 48)),
                      ),
                      Positioned(top: 8, right: 8, child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          borderRadius: BorderRadius.circular(20),
                          onTap: onUnsave,
                          child: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.85), shape: BoxShape.circle),
                            child: const Icon(Icons.favorite, size: 22, color: Colors.red),
                          ),
                        ),
                      )),
                    ],
                  ),
                )
              else
                Container(
                  height: 120, width: double.infinity, color: Colors.grey[50],
                  child: Stack(children: [
                    Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Icon(Icons.image_outlined, size: 40, color: Colors.grey[300]),
                      const SizedBox(height: 8),
                      Text('No image available', style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                    ])),
                    Positioned(top: 8, right: 8, child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(20), onTap: onUnsave,
                        child: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.85), shape: BoxShape.circle),
                          child: const Icon(Icons.favorite, size: 22, color: Colors.red),
                        ),
                      ),
                    )),
                  ]),
                ),

              // Details
              Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(color: _categoryColor.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(6)),
                        child: Text(_categoryLabel, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: _categoryColor)),
                      ),
                      const Spacer(),
                      if (place.rating > 0)
                        Row(children: [
                          Icon(Icons.star_rounded, size: 16, color: Colors.amber[700]),
                          const SizedBox(width: 3),
                          Text(place.rating.toStringAsFixed(1), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        ]),
                    ]),
                    const SizedBox(height: 10),
                    Text(place.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.black87), maxLines: 1, overflow: TextOverflow.ellipsis),
                    if (place.description != null && place.description!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(place.description!.length > 120 ? '${place.description!.substring(0, 117)}...' : place.description!,
                          style: TextStyle(fontSize: 13, color: Colors.grey[600], height: 1.3), maxLines: 2, overflow: TextOverflow.ellipsis),
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
