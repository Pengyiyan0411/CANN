// Contract recorder, not CANN tiling. Only used by host CPU checks.
namespace matmul_tiling {
enum class TPosition { GM, VECIN };
enum class CubeFormat { ND };
enum class DataType { DT_FLOAT16, DT_BFLOAT16, DT_FLOAT };
enum class MatrixTraverse { FIRSTN };
struct TilingRecord {
    int dim=0,M=0,N=0,K=0,sm=0,sn=0,sk=0,bm=0,bn=0,ub=0;
    bool ta=false,tb=false,vec=false,traverse=false;
    DataType a=DataType::DT_FLOAT,b=DataType::DT_FLOAT;
};
inline TilingRecord record;
inline int reject=0;
struct MultiCoreMatmulTiling {
    MultiCoreMatmulTiling(){record={};}
    int SetDim(int d){record.dim=d;return reject==1?-1:0;}
    void SetAType(TPosition,CubeFormat,DataType d,bool t){record.ta=t;record.a=d;}
    void SetBType(TPosition,CubeFormat,DataType d,bool t){record.tb=t;record.b=d;}
    void SetCType(TPosition p,CubeFormat,DataType){record.vec=p==TPosition::VECIN;}
    void SetOrgShape(int m,int n,int k){record.M=m;record.N=n;record.K=k;}
    void SetShape(int m,int n,int k){record.sm=m;record.sn=n;record.sk=k;}
    int SetSingleShape(int m,int n,int k){
        Mock::need(record.sm==m&&record.sn==n&&record.sk==k,"host shape mismatch");
        return reject==2?-1:0;
    }
    int SetFixSplit(int m,int n,int){record.bm=m;record.bn=n;return reject==3?-1:0;}
    int SetTraverse(MatrixTraverse){record.traverse=true;return reject==4?-1:0;}
    void EnableBias(bool bias){Mock::need(!bias,"unexpected bias");}
    void SetBufferSpace(int,int,int ub){record.ub=ub;}
    int GetTiling(TCubeTiling& td){
        td.baseM=record.bm;td.baseN=record.bn;td.baseK=32;
        td.singleCoreM=record.sm;td.singleCoreN=record.sn;td.singleCoreK=record.sk;
        td.usedCoreNum=1;td.stepM=(record.sm+record.bm-1)/record.bm;
        td.stepN=1;td.iterateOrder=1;
        if(reject==6)td.usedCoreNum=2;
        if(reject==7)td.baseN/=2;
        if(reject==8)td.singleCoreK-=8;
        if(reject==9)td.stepM=0;
        if(reject==10)td.iterateOrder=3;
        return reject==5?-1:0;
    }
};
}
