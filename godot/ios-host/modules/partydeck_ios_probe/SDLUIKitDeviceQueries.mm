/*
  Simple DirectMedia Layer
  Copyright (C) 1997-2025 Sam Lantinga <slouken@libsdl.org>

  This software is provided 'as-is', without any express or implied
  warranty.  In no event will the authors be held liable for any damages
  arising from the use of this software.

  Permission is granted to anyone to use this software for any purpose,
  including commercial applications, and to alter it and redistribute it
  freely, subject to the following restrictions:

  1. The origin of this software must not be misrepresented; you must not
     claim that you wrote the original software. If you use this software
     in a product, an acknowledgment in the product documentation would be
     appreciated but is not required.
  2. Altered source versions must be plainly marked as such, and must not be
     misrepresented as being the original software.
  3. This notice may not be removed or altered from any source distribution.
*/

// Altered source: only the two device queries are extracted from SDL 3.2.28's
// UIKit video file, which Godot's reduced SDL source set does not include.
// Their query bodies are unchanged. C linkage is explicit because this host
// compiles the extraction as Objective-C++ rather than Objective-C.
// Source commit: 7f3ae3d57459e59943a4ecfefc8f6277ec6bf540
// https://github.com/libsdl-org/SDL/blob/7f3ae3d57459e59943a4ecfefc8f6277ec6bf540/src/video/uikit/SDL_uikitvideo.m
// Full source SHA-256: e42cc222f7c551fe2100ff98ce1035db6c2d6c164bb585bc5b2d3d8456d2ef31

#import <UIKit/UIKit.h>

extern "C" bool SDL_IsIPad(void) {
	return ([UIDevice currentDevice].userInterfaceIdiom == UIUserInterfaceIdiomPad);
}

extern "C" bool SDL_IsAppleTV(void) {
	return ([UIDevice currentDevice].userInterfaceIdiom == UIUserInterfaceIdiomTV);
}
