/* Independent logical-pixel oracle for row consumers. The production byte
 * primitive is tested separately against this operation on a full framebuffer. */
void ew_pixel(int x, int y, int color);
void ew_row1(int x, int y, const unsigned char *line, const unsigned char *mask,
             unsigned source_bit, int width, int inverse)
{
    int i;
    for (i = 0; i < width; ++i, ++source_bit)
        if (!mask || (mask[source_bit / 8] & (128 >> (source_bit % 8))))
            ew_pixel(x + i, y, !!(line[source_bit / 8] & (128 >> (source_bit % 8))) ^ !!inverse);
}
