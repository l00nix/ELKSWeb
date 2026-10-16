#!/usr/bin/env python3
"""Derive a compact eight-row body face from independently licensed X.Org BDF.

Keep established advance widths, sample original BDF into physical columns,
then apply independently drawn numeral/t and horizontal stroke hints.
Regular columns are balanced; bold derives from regular BDF shapes with
one physical pixel added. Packed rows use one or two bytes according to width.
"""
from pathlib import Path
from generate import read_font
HERE=Path(__file__).resolve().parent

def legacy_body_glyphs(name,bold):
    result=[]
    for code,(advance,bearing,rows) in enumerate(read_font(HERE/name),32):
        cols=[x for x in range(8) if any(row&(128>>x) for row in rows)]
        if not cols:
            result.append((3,[0]*8));continue
        lo,hi=min(cols),max(cols);width=hi-lo+1;target=width
        c=chr(code)
        if 'a'<=c<='z' and c not in 'mw':
            target=min(width,4 if bold else (2 if c in 'frt' else 3))
        converted=[]
        # BDF top/bottom padding is one row each. Fold rare edge pixels inward.
        clipped=rows[1:9];clipped[0]|=rows[0];clipped[-1]|=rows[9]
        for row in clipped:
            bits=0
            for x in range(lo,hi+1):
                if row&(128>>x):
                    # Preserve endpoints and center interior strokes when
                    # narrowing. Left-stem f/r keep their distinct hook shape.
                    if c in 'fr': mapped=(x-lo)*target//width
                    else: mapped=((x-lo)*(target-1)+(width-1)//2)//(width-1) if width>1 else 0
                    bits|=128>>mapped
            converted.append(bits)
        # Narrowing the four-column BDF 'a' merges both bowl edges and closes
        # its counter. Redraw that counter explicitly in the three-column
        # body cell; keep the original advance and baseline.
        if not bold and c == 'a':
            converted = [0, 0, 0x60, 0x20, 0x60, 0xa0, 0x60, 0]
        result.append((target*2+1,converted))
    return result


def _source_rows(code):
    _,_,rows=read_font(HERE/'helvR08.bdf')[code-32]
    columns=[x for x in range(8) if any(row&(128>>x) for row in rows)]
    if not columns:return [[0] for _ in range(8)]
    clipped=rows[1:9];clipped[0]|=rows[0];clipped[-1]|=rows[9]
    return [[int(bool(row&(128>>x))) for x in range(min(columns),max(columns)+1)] for row in clipped]


def _resize_columns(rows,width):
    source=len(rows[0])
    return [[row[min(source-1,((2*x+1)*source)//(2*width))] for x in range(width)] for row in rows]


# Original numeral hints drawn for ELKSWeb; not reference-browser assets.
HINTS={
 '0':['0110','1001','1001','1001','1001','0110'],
 '1':['01','11','01','01','01','11'],
 '2':['0110','1001','0001','0010','0100','1111'],
 '3':['110','001','011','001','001','110'],
 '4':['0010','0110','1010','1111','0010','0010'],
 '5':['111','100','110','001','101','010'],
 '6':['0110','1000','1110','1001','1001','0110'],
 '7':['1111','0001','0010','0010','0100','0100'],
 '8':['0110','1001','0110','1001','1001','0110'],
 '9':['0110','1001','1001','0111','0001','0110'],
}



def _body_base(name,bold):
    result=[]
    for code,(advance,legacy_rows) in enumerate(legacy_body_glyphs(name,bold),32):
        width=advance-1;c=chr(code)
        if not bold and c=='a':
            rows=[[int(bool(row&(128>>(x//2)))) for x in range(width)] for row in legacy_rows]
        else:
            if c=='t':
                rows=[[int(v) for v in line] for line in
                      ['0110','0110','1111','0110','0110','0110','0011','0000']]
            elif c in HINTS:
                strings=HINTS[c];rows=[[0]*len(strings[0])]
                rows.extend([[int(v) for v in line] for line in strings]);rows.append([0]*len(strings[0]))
            else:rows=_source_rows(code)
            if bold:
                rows=_resize_columns(rows,max(1,width-1))
                rows=[[int((x<len(row) and row[x]) or (x>0 and row[x-1])) for x in range(width)] for row in rows]
            else:rows=_resize_columns(rows,width)
        result.append((advance,[sum(v<<(15-x) for x,v in enumerate(row)) for row in rows]))
    return result


def _balanced_columns(rows,width):
    """Distribute replicated BDF columns symmetrically, retaining endpoints."""
    source=len(rows[0]);weights=[width//source]*source
    extra=width%source
    if extra%2 and source%2:
        weights[source//2]+=1;extra-=1
    left,right=0,source-1
    while extra:
        weights[left]+=1;extra-=1
        if extra:weights[right]+=1;extra-=1
        left+=1;right-=1
    return [[v for v,n in zip(row,weights) for _ in range(n)] for row in rows]


def body_glyphs(name,bold):
    glyphs=_body_base(name,bold)
    if bold:return glyphs
    result=[]
    for code,(advance,rows) in enumerate(glyphs,32):
        c=chr(code);width=advance-1
        if c not in HINTS and c not in 'at':
            sampled=_balanced_columns(_source_rows(code),width)
            rows=[sum(v<<(15-x) for x,v in enumerate(row)) for row in sampled]
        original=rows[:]
        if c.isalpha() and c not in 'AVWXYkvwxy' and width>=6:
            for y,bits in enumerate(original):
                ink=[x for x in range(width) if bits&(0x8000>>x)]
                if len(ink)<2 or len(ink)!=ink[-1]-ink[0]+1:continue
                if (y and bits==original[y-1]) or (y<7 and bits==original[y+1]):continue
                # Original hint: extend isolated bars/round shoulders without
                # widening repeated vertical stems or closing their counters.
                if ink[0]>0:rows[y]|=0x8000>>(ink[0]-1)
                if ink[-1]<width-1:rows[y]|=0x8000>>(ink[-1]+1)
        result.append((advance,rows))
    return result


def small_regular_glyphs():
    """Six-row regular face: preserve counters instead of merging row strokes."""
    result=[]
    for code,(advance,_) in enumerate(body_glyphs('helvR08.bdf',0),32):
        width=(advance*3+2)//4-1
        rows=_source_rows(code);c=chr(code)
        if c=='a':
            rows=[[int(v) for v in row] for row in
                  ['000','000','011','001','011','101','011','000']]
        if c in HINTS:
            rows=[[int(v) for v in row] for row in HINTS[c]]
        elif c.isupper():
            rows=rows[:7]
            remove=next((r for r in range(1,6)
                         if rows[r]==rows[r-1] or rows[r]==rows[r+1]),3)
            rows.pop(remove)
        elif c=='j': rows=[rows[i] for i in (0,1,2,4,6,7)]
        elif c in 'il': rows=[rows[i] for i in (0,1,2,3,5,6)]
        elif c in 'gpqy':
            rows=[rows[0],rows[2],rows[3],rows[4],rows[5],
                  [a|b for a,b in zip(rows[6],rows[7])]]
        elif c.islower(): rows=[rows[i] for i in (0,2,3,4,5,6)]
        else:
            rows=[rows[0],rows[1],[a|b for a,b in zip(rows[2],rows[3])],
                  rows[4],rows[5],[a|b for a,b in zip(rows[6],rows[7])]]
        rows=_resize_columns(rows,width)
        result.append((width+1,[sum(v<<(15-x) for x,v in enumerate(row)) for row in rows]))
    return result


def generate():
    glyphs=body_glyphs('helvR08.bdf',0)+body_glyphs('helvB08.bdf',1)
    offsets=[];data=[]
    for advance,rows in glyphs:
        offsets.append(len(data))
        for row in rows:
            data.append(row>>8)
            if advance>9:data.append(row&255)
    small=small_regular_glyphs()
    small_offsets=[];small_data=[]
    for advance,rows in small:
        small_offsets.append(len(small_data))
        for row in rows:
            small_data.append(row>>8)
            if advance>9:small_data.append(row&255)
    out=['/* Generated by font/generate_body.py; independent X.Org Adobe/DEC BDF.',
         ' * Adobe/DEC font license: font/COPYING. Original hints/runtime: GPL-2.0-or-later.',
         ' * Packed body table: %d bytes (advances190 + offsets380 + pixels%d).'%(570+len(data),len(data)),
         ' * Packed regular small table: %d bytes (offsets190 + pixels%d); total %d. */'%(190+len(small_data),len(small_data),760+len(data)+len(small_data)),
         '#include "body_font.h"','#include "../platform/elks_platform.h"']
    for typename,name,values,fmt in [('unsigned char','body_advances',[g[0] for g in glyphs],'%d'),
                                    ('unsigned short','body_offsets',offsets,'%d'),
                                    ('unsigned char','body_pixels',data,'0x%02x'),
                                    ('unsigned short','small_offsets',small_offsets,'%d'),
                                    ('unsigned char','small_pixels',small_data,'0x%02x')]:
        out.append('static const %s %s[%d] = {'%(typename,name,len(values)))
        for i in range(0,len(values),16):out.append(' '+','.join(fmt%v for v in values[i:i+16])+',')
        out.append('};')
    out.append(r'''
static unsigned body_for(unsigned char c,int bold)
{
    if(c==160)c=' ';
    if(c<32||c>126)c='?';
    return (bold?95:0)+c-32;
}
static unsigned body_row(unsigned glyph,int row)
{
    unsigned offset=body_offsets[glyph]+row*(body_advances[glyph]>9?2:1);
    unsigned bits=(unsigned)body_pixels[offset]<<8;
    if(body_advances[glyph]>9)bits|=body_pixels[offset+1];
    return bits;
}
int ew_body_char_width(unsigned char c,int bold) { return body_advances[body_for(c,bold)]; }
int ew_body_height(int bold) { (void)bold; return 8; }
int ew_body_width(const char EW_FONT_FAR *text,unsigned count,int bold)
{
    unsigned width=0;
    while(count--&&*text){unsigned advance=ew_body_char_width((unsigned char)*text++,bold);
        if(width>32767U-advance)return 32767;
        width+=advance;
    }
    return (int)width;
}
void ew_body_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic)
{
    unsigned glyph=body_for(c,bold),bits;
    int advance=body_advances[glyph],row,column,skew;
    if(x < -18 || x>=EW_SCREEN_WIDTH || y<=-8 || y>=EW_SCREEN_HEIGHT)return;
    if(bg>=0)ew_fillrect(x,y,advance,8,bg);
    for(row=0;row<8;row++){
        bits=body_row(glyph,row);skew=italic?(7-row)/4:0;
        for(column=0;column<advance-1;column++,bits<<=1)if(bits&0x8000U)
            ew_pixel(x+1+column+skew,y+row,fg);
    }
}
int ew_small_char_width(unsigned char c,int bold)
{
    return (ew_body_char_width(c,bold)*3+2)/4;
}
int ew_small_height(int bold) { (void)bold; return 6; }
int ew_small_width(const char EW_FONT_FAR *text,unsigned count,int bold)
{
    unsigned width=0;
    while(count--&&*text){unsigned advance=ew_small_char_width((unsigned char)*text++,bold);
        if(width>32767U-advance)return 32767;
        width+=advance;
    }
    return (int)width;
}
void ew_small_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic)
{
    unsigned glyph=body_for(c,bold),bits;
    int row,column,skew,advance,ink_width,dx,dy;
    unsigned offset;
    if(x < -14 || x>=EW_SCREEN_WIDTH || y<=-6 || y>=EW_SCREEN_HEIGHT)return;
    advance=ew_small_char_width(c,bold);ink_width=body_advances[glyph]-1;
    if(bg>=0)ew_fillrect(x,y,advance,6,bg);
    if(!bold){
        offset=small_offsets[glyph];
        for(row=0;row<6;row++){
            bits=(unsigned)small_pixels[offset++]<<8;
            if(advance>9)bits|=small_pixels[offset++];
            skew=italic?(5-row)/4:0;
            for(column=0;column<advance-1;column++,bits<<=1)if(bits&0x8000U){
                dx=column+skew;if(dx>advance-2)dx=advance-2;
                ew_pixel(x+dx,y+row,fg);
            }
        }
        return;
    }
    for(row=0;row<8;row++){
        bits=body_row(glyph,row);skew=italic?(7-row)/4:0;dy=row*3/4;
        if(c=='i'||c=='j'){
            if(row==1)continue;
            if(row>=2)dy=2+(row-2)*3/(c=='i'?4:5);
            if(dy>5)continue;
        }
        for(column=0;column<ink_width;column++,bits<<=1)if(bits&0x8000U){
            dx=(column*(advance-2)+(ink_width-1)/2)/(ink_width-1)+skew;
            if(dx>advance-2)dx=advance-2;
            ew_pixel(x+dx,y+dy,fg);
        }
    }
}
int ew_mono_char_width(unsigned char c,int bold,int size)
{
    (void)c;
    return (size==0?8:size==2?12:9)+(bold?1:0);
}
int ew_mono_height(int size) { return size==0?6:size==2?10:8; }
int ew_mono_width(const char EW_FONT_FAR *text,unsigned count,int bold,int size)
{
    unsigned width=0,advance=ew_mono_char_width(' ',bold,size);
    while(count--&&*text++){
        if(width>32767U-advance)return 32767;
        width+=advance;
    }
    return (int)width;
}
void ew_mono_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic,int size)
{
    unsigned glyph=body_for(c,bold),bits;
    int advance=ew_mono_char_width(c,bold,size),height=ew_mono_height(size);
    int source_width=body_advances[glyph]-1,ink_width,left,row,col,dx,dy,end,skew;
    if(x < -14 || x>=EW_SCREEN_WIDTH || y<=-10 || y>=EW_SCREEN_HEIGHT)return;
    if(bg>=0)ew_fillrect(x,y,advance,height,bg);
    ink_width=source_width<advance-2?source_width:advance-2;left=(advance-ink_width)/2;
    for(row=0;row<8;row++){
        bits=body_row(glyph,row);dy=row*height/8;end=(row+1)*height/8;
        if(end<=dy)end=dy+1;
        if(size==0&&(c=='i'||c=='j')){
            if(row==1)continue;
            if(row>=2)dy=2+(row-2)*3/(c=='i'?4:5);
            if(dy>=height)continue;
            end=dy+1;
        }
        skew=italic?(7-row)/4:0;
        for(col=0;col<source_width;col++,bits<<=1)if(bits&0x8000U){
            dx=(col*(ink_width-1)+(source_width-1)/2)/(source_width-1)+left+skew;
            if(dx>advance-2)dx=advance-2;
            ew_vline(x+dx,y+dy,end-dy,fg);
        }
    }
}
''')
    return '\n'.join(out)

if __name__=='__main__':(HERE/'body_font.c').write_text(generate())
