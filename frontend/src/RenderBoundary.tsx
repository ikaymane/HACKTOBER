import {Component,type ReactNode} from 'react';
export default class RenderBoundary extends Component<{children:ReactNode;label:string},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 componentDidCatch(error:Error){console.error('3D renderer:',error.message);}
 render(){return this.state.failed?<div className="render-error" role="status"><strong>{this.props.label}</strong><p>Le rendu 3D est indisponible sur cet appareil. Les diagnostics et les données restent accessibles.</p><button onClick={()=>this.setState({failed:false})}>Réessayer le rendu</button></div>:this.props.children;}
}
