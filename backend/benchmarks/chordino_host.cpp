// Standalone Chordino CLI host. SPDX-License-Identifier: GPL-2.0-or-later
// Linked Chordino is GPL; the app invokes this separate executable.
#include "Chordino.h"
#include <vamp-sdk/FFT.h>
#include <fstream>
#include <vector>
#include <cmath>
#include <iostream>
#include <iomanip>
int main(int argc,char **argv) {
 if(argc!=3)return 2;
 const int sr=std::stoi(argv[2]);
 std::ifstream file(argv[1],std::ios::binary|std::ios::ate);
 if(!file)return 3;
 auto count=static_cast<size_t>(file.tellg())/sizeof(float);file.seekg(0);
 std::vector<float> y(count);file.read(reinterpret_cast<char*>(y.data()),count*sizeof(float));
 Chordino plugin(sr);auto n=plugin.getPreferredBlockSize(),hop=plugin.getPreferredStepSize();
 if(!plugin.initialise(1,hop,n))return 4;
 plugin.getOutputDescriptors();
 Vamp::FFTReal fft(n);std::vector<double> window(n),spectrum(n+2);std::vector<float> input(n+2);
 auto emit=[](const Vamp::Plugin::FeatureSet& features){auto it=features.find(0);if(it==features.end())return;for(auto &f:it->second)std::cout<<std::fixed<<std::setprecision(6)<<f.timestamp.sec+f.timestamp.nsec/1e9<<'\t'<<f.label<<'\n';};
 for(size_t center=0;center<count;center+=hop){
  for(unsigned i=0;i<n;i++){long pos=static_cast<long>(center)+i-n/2;window[i]=(pos>=0&&pos<static_cast<long>(count)?y[pos]:0)*(.5-.5*std::cos(2*M_PI*i/n));}
  fft.forward(window.data(),spectrum.data());for(unsigned i=0;i<n+2;i++)input[i]=spectrum[i];
  const float *channels[]={input.data()};emit(plugin.process(channels,Vamp::RealTime::fromSeconds(static_cast<double>(center)/sr)));
 }
 emit(plugin.getRemainingFeatures());return 0;
}
