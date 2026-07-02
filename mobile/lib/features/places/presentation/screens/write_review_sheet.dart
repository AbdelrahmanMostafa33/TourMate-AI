import 'package:flutter/material.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../app/app_theme.dart';

/// Bottom sheet for writing or editing a review.
/// When [initialRating] and [initialComment] are provided, it operates in edit mode.
class WriteReviewSheet extends StatefulWidget {
  final String placeId;
  final bool isEditing;
  final int? initialRating;
  final String? initialComment;
  final void Function({required int rating, String? comment}) onSubmit;

  const WriteReviewSheet({
    super.key,
    required this.placeId,
    this.isEditing = false,
    this.initialRating,
    this.initialComment,
    required this.onSubmit,
  });

  @override
  State<WriteReviewSheet> createState() => _WriteReviewSheetState();
}

class _WriteReviewSheetState extends State<WriteReviewSheet> {
  TourMateColors get tm => context.tm;
  late int _rating;
  late TextEditingController _commentController;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _rating = widget.initialRating ?? 0;
    _commentController =
        TextEditingController(text: widget.initialComment ?? '');
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl5, Spacing.xl, Spacing.xl5, Spacing.xl7),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: tm.border,
                borderRadius: BorderRadius.circular(Spacing.xxs),
              ),
            ),
          ),

          const SizedBox(height: Spacing.xl4),

          // Title
          Center(
            child: Text(
              widget.isEditing ? 'Edit Review' : 'Write a Review',
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),

          const SizedBox(height: Spacing.xl5),

          // Star rating
          Center(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(5, (i) {
                final starNum = i + 1;
                return GestureDetector(
                  onTap: () => setState(() => _rating = starNum),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: Spacing.sm),
                    child: AnimatedScale(
                      scale: starNum <= _rating ? 1.1 : 1.0,
                      duration: const Duration(milliseconds: 150),
                      child: Icon(
                        starNum <= _rating
                            ? Icons.star_rounded
                            : Icons.star_border_rounded,
                        size: 40,
                        color: starNum <= _rating
                            ? tm.sapphire
                            : tm.border,
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),

          if (_rating > 0) ...[
            const SizedBox(height: Spacing.md),
            Center(
              child: Text(
                _ratingLabel(_rating),
                style: TextStyle(
                  fontSize: 14,
                  color: tm.textSecondary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],

          const SizedBox(height: Spacing.xl5),

          // Comment field
          TextField(
            controller: _commentController,
            maxLines: 4,
            maxLength: 500,
            decoration: InputDecoration(
              hintText: 'Share your experience...',
              hintStyle: TextStyle(color: tm.textTertiary),
              filled: true,
              fillColor: tm.surface,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tm.border),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tm.border),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: tm.pureBlack, width: 1.5),
              ),
              contentPadding: const EdgeInsets.all(16),
            ),
            style: const TextStyle(fontSize: 14),
          ),

          const SizedBox(height: Spacing.xl3),

          // Submit button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: (_rating == 0 || _submitting)
                  ? null
                  : () {
                      setState(() => _submitting = true);
                      widget.onSubmit(
                        rating: _rating,
                        comment: _commentController.text.trim().isEmpty
                            ? null
                            : _commentController.text.trim(),
                      );
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: tm.pureBlack,
                foregroundColor: tm.pureWhite,
                disabledBackgroundColor: tm.border,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl2),
                ),
                padding: const EdgeInsets.symmetric(vertical: Spacing.xl3),
              ),
              child: _submitting
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        color: tm.pureWhite,
                        strokeWidth: 2,
                      ),
                    )
                  : Text(
                      widget.isEditing ? 'Save Changes' : 'Submit Review',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  String _ratingLabel(int rating) {
    switch (rating) {
      case 1:
        return 'Poor';
      case 2:
        return 'Fair';
      case 3:
        return 'Good';
      case 4:
        return 'Very Good';
      case 5:
        return 'Excellent';
      default:
        return '';
    }
  }
}
